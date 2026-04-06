"""Temporal activities for Claude Agents SDK integration."""

from __future__ import annotations

import os
import dataclasses
from typing import Any

from temporalio import activity
from claude_agent_sdk import AgentDefinition, ClaudeSDKClient, ClaudeAgentOptions

from agentex.lib.utils.logging import make_logger
from agentex.lib.core.temporal.plugins.claude_agents.hooks import create_streaming_hooks
from agentex.lib.core.temporal.plugins.claude_agents.message_handler import ClaudeMessageHandler
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
                description=agent_data.get('description', ''),
                prompt=agent_data.get('prompt', ''),
                tools=agent_data.get('tools'),
                model=agent_data.get('model'),
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

    This activity:
    1. Gets task_id from ContextVar (set by ContextInterceptor)
    2. Configures Claude with workspace isolation and session resume
    3. Runs Claude SDK and processes messages via ClaudeMessageHandler
    4. Streams messages to UI in real-time
    5. Returns session_id, usage, and cost for next turn

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
    # so claude_options values for system_prompt/resume/agents are not masked.
    explicit_params: dict[str, Any] = {k: v for k, v in {
        "cwd": workspace_path,
        "allowed_tools": allowed_tools,
        "permission_mode": permission_mode,
        "system_prompt": system_prompt,
        "resume": resume_session_id,
        "agents": agent_defs,
    }.items() if v is not None}

    # Merge in any additional claude_options (explicit params take precedence)
    if claude_options:
        claude_options = dict(claude_options)  # avoid mutating caller's dict
        if "agents" in claude_options:
            claude_options["agents"] = _reconstruct_agent_defs(claude_options["agents"])
        options_dict = {**claude_options, **explicit_params}
    else:
        options_dict = explicit_params

    # Apply default for permission_mode if neither source supplied a value
    if "permission_mode" not in options_dict:
        options_dict["permission_mode"] = "acceptEdits"

    # Create hooks for streaming tool calls and subagent execution
    streaming_hooks = create_streaming_hooks(
        task_id=task_id,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
    )

    # Merge streaming hooks with any user-provided hooks from claude_options
    user_hooks = options_dict.pop("hooks", None)
    if user_hooks:
        merged_hooks = dict(streaming_hooks)
        for event, matchers in user_hooks.items():
            if event in merged_hooks:
                merged_hooks[event] = merged_hooks[event] + matchers
            else:
                merged_hooks[event] = matchers
        options_dict["hooks"] = merged_hooks
    else:
        options_dict["hooks"] = streaming_hooks

    # Construct ClaudeAgentOptions — any SDK field works via claude_options
    options = ClaudeAgentOptions(**options_dict)

    # Create message handler for streaming
    handler = ClaudeMessageHandler(
        task_id=task_id,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
    )

    # Run Claude and process messages
    try:
        await handler.initialize()

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            # Use receive_response() instead of receive_messages()
            # receive_response() yields messages until ResultMessage, then stops
            # receive_messages() is infinite and never completes!
            async for message in client.receive_response():
                await handler.handle_message(message)

        logger.debug(f"Message loop completed, cleaning up...")
        await handler.cleanup()

        results = handler.get_results()
        logger.debug(f"Returning results with keys: {results.keys()}")
        return results

    except Exception as e:
        logger.error(f"[run_claude_agent_activity] Error: {e}", exc_info=True)
        await handler.cleanup()
        raise
