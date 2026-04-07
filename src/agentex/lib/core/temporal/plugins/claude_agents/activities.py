"""Temporal activities for Claude Agents SDK integration.

Processes all content blocks from the AssistantMessage stream in iteration order
(TextBlock, ThinkingBlock, ToolUseBlock) with correct timestamps. Tool results
come from PostToolUse/PostToolUseFailure hooks which fire between message yields.
"""

from __future__ import annotations

import os
import dataclasses
from typing import Any

from temporalio import activity
from claude_agent_sdk import AgentDefinition, ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.types import (
    HookEvent,
    TextBlock,
    HookMatcher,
    ToolUseBlock,
    ResultMessage,
    SystemMessage,
    ThinkingBlock,
    AssistantMessage,
)

from agentex.lib import adk
from agentex.types.text_delta import TextDelta
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.task_message_update import StreamTaskMessageFull, StreamTaskMessageDelta
from agentex.types.tool_request_content import ToolRequestContent
from agentex.lib.core.temporal.plugins.claude_agents.hooks.hooks import create_streaming_hooks
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import (
    streaming_task_id,
    streaming_trace_id,
    streaming_parent_span_id,
)

logger = make_logger(__name__)

# Fields that are not serializable across the Temporal boundary and should be
# excluded from claude_options_to_dict output.
_NON_SERIALIZABLE_FIELDS = {"debug_stderr", "stderr", "can_use_tool", "hooks"}


def claude_options_to_dict(options: ClaudeAgentOptions) -> dict[str, Any]:
    """Convert a ClaudeAgentOptions to a Temporal-serializable dict.

    Use this at the workflow call site so you get full type safety and
    autocomplete when constructing options, while Temporal gets a plain dict.

    Non-serializable fields (callbacks, file objects, hooks) are excluded —
    the activity injects AgentEx streaming hooks automatically.

    Example::

        extra = ClaudeAgentOptions(
            mcp_servers={"my-server": McpServerConfig(command="npx", args=[...])},
            model="sonnet",
        )

        result = await workflow.execute_activity(
            run_claude_agent_activity,
            args=[prompt, workspace, tools, "acceptEdits", None, None, None,
                  claude_options_to_dict(extra)],
            ...
        )
    """
    result = {}
    for field in dataclasses.fields(options):
        if field.name in _NON_SERIALIZABLE_FIELDS:
            continue
        value = getattr(options, field.name)
        # Skip fields left at their default to keep the dict minimal
        if value == field.default or (
            callable(field.default_factory) and value == field.default_factory()  # type: ignore[arg-type]
        ):
            continue
        result[field.name] = value
    return result


def _reconstruct_agent_defs(agents: dict[str, Any] | None) -> dict[str, AgentDefinition] | None:
    """Reconstruct AgentDefinition objects from Temporal-serialized dicts."""
    if not agents:
        return None
    agent_defs = {}
    for name, agent_data in agents.items():
        if isinstance(agent_data, AgentDefinition):
            agent_defs[name] = agent_data
        else:
            agent_defs[name] = AgentDefinition(
                description=agent_data.get("description", ""),
                prompt=agent_data.get("prompt", ""),
                tools=agent_data.get("tools"),
                model=agent_data.get("model"),
            )
    return agent_defs


@activity.defn
async def create_workspace_directory(task_id: str, workspace_root: str | None = None) -> str:
    """Create workspace directory for task - runs as Temporal activity

    Args:
        task_id: Task ID for workspace directory name
        workspace_root: Root directory for workspaces (defaults to .claude-workspace/ in cwd)

    Returns:
        Absolute path to created workspace
    """
    if workspace_root is None:
        # Default to .claude-workspace in current directory
        # Follows Claude SDK's .claude/ convention
        workspace_root = os.path.join(os.getcwd(), ".claude-workspace")

    workspace_path = os.path.join(workspace_root, task_id)
    os.makedirs(workspace_path, exist_ok=True)
    logger.info(f"Created workspace: {workspace_path}")
    return workspace_path


@activity.defn(name="run_claude_agent_activity")
async def run_claude_agent_activity(
    prompt: str,
    workspace_path: str,
    allowed_tools: list[str],
    permission_mode: str | None = None,
    system_prompt: str | None = None,
    resume_session_id: str | None = None,
    agents: dict[str, Any] | None = None,
    claude_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute Claude SDK - wrapped in Temporal activity.

    Streams all content block types to the Agentex UI:
    - TextBlock → streamed as text deltas (from message stream)
    - ThinkingBlock → streamed as ReasoningContent (from message stream)
    - ToolUseBlock → streamed as tool_request (from message stream)
    - Tool results → streamed as tool_response (from PostToolUse hook)

    Args:
        prompt: User message to send to Claude
        workspace_path: Directory for file operations (cwd)
        allowed_tools: List of tools Claude can use (include "Task" for subagents)
        permission_mode: Permission mode (default: acceptEdits)
        system_prompt: Optional system prompt override
        resume_session_id: Optional session ID to resume conversation context
        agents: Optional dict of subagent definitions for Task tool
        claude_options: Optional dict of additional ClaudeAgentOptions kwargs.
            Any field supported by the Claude SDK can be passed here
            (e.g. mcp_servers, model, max_turns, max_budget_usd, etc.).
            These are merged with the explicit params above, with explicit
            params taking precedence.

    Returns:
        dict with "messages", "session_id", "usage", and "cost_usd" keys
    """

    # Get streaming context from ContextVars (set by interceptor)
    task_id = streaming_task_id.get()
    trace_id = streaming_trace_id.get()
    parent_span_id = streaming_parent_span_id.get()

    logger.info(
        f"[run_claude_agent_activity] Starting - "
        f"task_id={task_id}, workspace={workspace_path}, tools={allowed_tools}, "
        f"resume={'YES' if resume_session_id else 'NO (new session)'}, "
        f"subagents={list(agents.keys()) if agents else 'NONE'}"
    )

    # Reconstruct AgentDefinition objects from serialized dicts
    # Temporal serializes dataclasses to dicts, need to recreate them
    agent_defs = _reconstruct_agent_defs(agents)

    # Only include explicit params that were actually supplied (non-None),
    # so claude_options values are not masked.
    explicit_params: dict[str, Any] = {
        k: v
        for k, v in {
            "cwd": workspace_path,
            "allowed_tools": allowed_tools,
            "permission_mode": permission_mode,
            "system_prompt": system_prompt,
            "resume": resume_session_id,
            "agents": agent_defs,
        }.items()
        if v is not None
    }

    # Merge in any additional claude_options (explicit params take precedence)
    if claude_options:
        claude_options = dict(claude_options)  # avoid mutating caller's dict
        if "agents" in claude_options:
            claude_options["agents"] = _reconstruct_agent_defs(claude_options["agents"])
        options_dict = {**claude_options, **explicit_params}
    else:
        options_dict = explicit_params

    if "permission_mode" not in options_dict:
        options_dict["permission_mode"] = "acceptEdits"

    # Shared subagent span tracking — hooks and message-level streaming both use this
    subagent_spans: dict[str, Any] = {}

    # PreToolUse: auto-allow permissions
    # PostToolUse/PostToolUseFailure: stream tool results (richer than ToolResultBlock)
    # Subagent spans tracked for Task tool tracing
    activity_hooks: dict[HookEvent, list[HookMatcher]] = create_streaming_hooks(
        task_id=task_id,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        subagent_spans=subagent_spans,
    )

    # Merge with any user-provided hooks from claude_options
    user_hooks = options_dict.pop("hooks", None)
    if user_hooks:
        for event, matchers in user_hooks.items():
            if event in activity_hooks:
                activity_hooks[event] = activity_hooks[event] + matchers  # type: ignore[operator]
            else:
                activity_hooks[event] = matchers  # type: ignore[assignment]

    options_dict["hooks"] = activity_hooks
    options = ClaudeAgentOptions(**options_dict)

    text_streaming_cm: Any = None  # the context manager itself
    text_streaming_ctx: Any = None  # the value returned by __aenter__
    session_id: str | None = None
    usage_info: dict[str, Any] | None = None
    cost_info: float | None = None
    serialized_messages: list[dict[str, Any]] = []

    async def close_text_stream() -> None:
        nonlocal text_streaming_cm, text_streaming_ctx
        if text_streaming_ctx and text_streaming_cm:
            try:
                await text_streaming_cm.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Failed to close text stream: {e}")
            text_streaming_cm = None
            text_streaming_ctx = None

    async def ensure_text_stream() -> Any:
        nonlocal text_streaming_cm, text_streaming_ctx
        if text_streaming_ctx is None and task_id:
            text_streaming_cm = adk.streaming.streaming_task_message_context(
                task_id=task_id,
                initial_content=TextContent(author="agent", content="", format="markdown"),
            )
            text_streaming_ctx = await text_streaming_cm.__aenter__()
        return text_streaming_ctx

    async def stream_text_delta(text: str) -> None:
        if not text:
            return
        ctx = await ensure_text_stream()
        if not ctx:
            return
        try:
            await ctx.stream_update(
                StreamTaskMessageDelta(
                    parent_task_message=ctx.task_message,
                    delta=TextDelta(type="text", text_delta=text),
                    type="delta",
                )
            )
        except Exception as e:
            logger.warning(f"Failed to stream text delta: {e}")

    async def stream_tool_request(block: ToolUseBlock) -> None:
        await close_text_stream()

        # Subagent tracing
        if block.name == "Task" and trace_id and parent_span_id:
            subagent_type = block.input.get("subagent_type", "unknown")
            logger.info(f"Subagent started: {subagent_type}")
            subagent_ctx = adk.tracing.span(
                trace_id=trace_id,
                parent_id=parent_span_id,
                name=f"Subagent: {subagent_type}",
                input=block.input,
            )
            subagent_span = await subagent_ctx.__aenter__()
            subagent_spans[block.id] = (subagent_ctx, subagent_span)

        if not task_id:
            return
        try:
            async with adk.streaming.streaming_task_message_context(
                task_id=task_id,
                initial_content=ToolRequestContent(
                    author="agent",
                    name=block.name,
                    arguments=block.input,
                    tool_call_id=block.id,
                ),
            ) as ctx:
                await ctx.stream_update(
                    StreamTaskMessageFull(
                        parent_task_message=ctx.task_message,
                        content=ToolRequestContent(
                            author="agent",
                            name=block.name,
                            arguments=block.input,
                            tool_call_id=block.id,
                        ),
                        type="full",
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to stream tool request: {e}")

    async def stream_reasoning(block: ThinkingBlock) -> None:
        if not task_id or not block.thinking:
            return
        lines = block.thinking.strip().split("\n", 1)
        summary = [lines[0]]
        content = ReasoningContent(
            author="agent",
            summary=summary,
            content=[block.thinking],
            style="static",
            type="reasoning",
        )
        try:
            async with adk.streaming.streaming_task_message_context(
                task_id=task_id,
                initial_content=content,
            ) as ctx:
                await ctx.stream_update(
                    StreamTaskMessageFull(
                        parent_task_message=ctx.task_message,
                        content=content,
                        type="full",
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to stream reasoning: {e}")

    async def handle_assistant_message(message: AssistantMessage) -> None:
        text_parts: list[str] = []
        for block in message.content:
            if isinstance(block, TextBlock):
                await stream_text_delta(block.text)
                if block.text:
                    text_parts.append(block.text)

            elif isinstance(block, ThinkingBlock):
                if block.thinking:
                    await close_text_stream()
                    await stream_reasoning(block)

            elif isinstance(block, ToolUseBlock):
                await stream_tool_request(block)

            # ToolResultBlock skipped — tool results come from PostToolUse hook

        if text_parts:
            serialized_messages.append(
                {
                    "role": "assistant",
                    "content": "\n".join(text_parts),
                }
            )

    async def handle_system_message(message: SystemMessage) -> None:
        nonlocal session_id
        if message.subtype == "init":
            session_id = message.data.get("session_id")
            logger.debug(f"Session initialized: {session_id[:16] if session_id else 'unknown'}...")

    async def handle_result_message(message: ResultMessage) -> None:
        nonlocal session_id, usage_info, cost_info
        usage_info = message.usage
        cost_info = message.total_cost_usd
        if message.session_id:
            session_id = message.session_id
        logger.info(f"Cost: ${cost_info:.4f}, Duration: {message.duration_ms}ms, Turns: {message.num_turns}")

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    await handle_assistant_message(message)
                elif isinstance(message, SystemMessage):
                    await handle_system_message(message)
                elif isinstance(message, ResultMessage):
                    await handle_result_message(message)

        logger.debug("Message loop completed, cleaning up...")
        await close_text_stream()

        results = {
            "messages": serialized_messages,
            "task_id": task_id,
            "session_id": session_id,
            "usage": usage_info,
            "cost_usd": cost_info,
        }
        logger.debug(f"Returning results with keys: {results.keys()}")
        return results

    except Exception as e:
        logger.error(f"[run_claude_agent_activity] Error: {e}", exc_info=True)
        await close_text_stream()
        for _ctx, _span in list(subagent_spans.values()):
            try:
                await _ctx.__aexit__(None, None, None)
            except Exception:
                pass
        subagent_spans.clear()
        raise
