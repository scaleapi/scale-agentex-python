"""Claude Agents SDK integration with Temporal - MVP v0

This module provides minimal integration between Claude Agents SDK and AgentEx's
Temporal-based architecture.

MVP v0 Features:
- Basic activity wrapper for Claude SDK calls
- Text streaming to Redis/UI
- Workspace isolation via cwd parameter
- Reuses OpenAI's ContextInterceptor for context threading

What's missing (see examples/tutorials/10_async/10_temporal/090_claude_agents_sdk_mvp/NEXT_STEPS.md):
- Automatic plugin (manual activity wrapping for now)
- Tool call streaming
- Tracing wrapper
- Subagents
- Tests
"""

from __future__ import annotations

from typing import Any
from datetime import timedelta

from temporalio import activity
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AgentDefinition,
    AssistantMessage,
    UserMessage,
    TextBlock,
    SystemMessage,
    ResultMessage,
    ToolUseBlock,
    ToolResultBlock,
)

# Reuse OpenAI's context threading - this is the key to streaming!
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import (
    ContextInterceptor,
    streaming_task_id,
    streaming_trace_id,
    streaming_parent_span_id,
)

from agentex.lib.utils.logging import make_logger
from agentex.lib import adk
from agentex.types.text_content import TextContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import StreamTaskMessageDelta, StreamTaskMessageFull

# Reuse OpenAI's lifecycle streaming activity
from agentex.lib.core.temporal.plugins.openai_agents.hooks.activities import stream_lifecycle_content

logger = make_logger(__name__)


@activity.defn(name="run_claude_agent_activity")
async def run_claude_agent_activity(
    prompt: str,
    workspace_path: str,
    allowed_tools: list[str],
    permission_mode: str = "acceptEdits",
    system_prompt: str | None = None,
    resume_session_id: str | None = None,
    agents: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute Claude SDK - wrapped in Temporal activity

    This activity:
    1. Gets task_id from ContextVar (set by ContextInterceptor)
    2. Configures Claude with workspace isolation and session resume
    3. Runs Claude SDK and collects responses
    4. Extracts and returns session_id for next turn
    5. Returns messages for Temporal determinism

    Args:
        prompt: User message to send to Claude
        workspace_path: Directory for file operations (cwd)
        allowed_tools: List of tools Claude can use (include "Task" for subagents)
        permission_mode: Permission mode (default: acceptEdits)
        system_prompt: Optional system prompt override
        resume_session_id: Optional session ID to resume conversation context
        agents: Optional dict of subagent definitions for Task tool

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
    agent_defs = None
    if agents:
        agent_defs = {}
        for name, agent_data in agents.items():
            if isinstance(agent_data, AgentDefinition):
                agent_defs[name] = agent_data
            else:
                # Reconstruct from dict
                agent_defs[name] = AgentDefinition(
                    description=agent_data.get('description', ''),
                    prompt=agent_data.get('prompt', ''),
                    tools=agent_data.get('tools'),
                    model=agent_data.get('model'),
                )

    # Configure Claude with workspace isolation, session resume, and subagents
    options = ClaudeAgentOptions(
        cwd=workspace_path,
        allowed_tools=allowed_tools,
        permission_mode=permission_mode,  # type: ignore
        system_prompt=system_prompt,
        resume=resume_session_id,  # Resume previous session for context!
        agents=agent_defs,  # Subagent definitions for Task tool!
    )

    # Run Claude and collect results
    messages = []
    streaming_ctx = None
    tool_call_map = {}  # Map tool_call_id → tool_name
    last_tool_call_id = None  # Track most recent tool call for matching results
    current_subagent_span = None  # Track active subagent span for setting output
    current_subagent_ctx = None  # Track context manager for proper cleanup

    try:
        # Only create streaming context if we have task_id
        if task_id:
            logger.info(f"[run_claude_agent_activity] Creating streaming context for task: {task_id}")
            streaming_ctx = await adk.streaming.streaming_task_message_context(
                task_id=task_id,
                initial_content=TextContent(
                    author="agent",
                    content="",
                    format="markdown"
                )
            ).__aenter__()

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            async for message in client.receive_messages():
                messages.append(message)

                # Debug: Log ALL message types and content blocks with sequence number
                msg_num = len(messages)
                logger.info(f"[run_claude_agent_activity] 📨 [{msg_num}] Message type: {type(message).__name__}")
                if isinstance(message, AssistantMessage):
                    block_types = [type(b).__name__ for b in message.content]
                    logger.info(f"[run_claude_agent_activity]    [{msg_num}] Content blocks: {block_types}")

                # Handle UserMessage as tool results (when permission_mode=acceptEdits)
                # Claude SDK auto-executes tools and returns results as UserMessage
                if isinstance(message, UserMessage) and last_tool_call_id and task_id:
                    tool_name = tool_call_map.get(last_tool_call_id, "unknown")
                    logger.info(f"[run_claude_agent_activity] ✅ [{msg_num}] STREAMING Tool result (UserMessage): {tool_name}")

                    # If this was a subagent (Task tool), close the subagent span
                    if tool_name == "Task" and current_subagent_span and current_subagent_ctx:
                        # Extract result for span output
                        user_content = message.content
                        if isinstance(user_content, list):
                            user_content = str(user_content)

                        current_subagent_span.output = {"result": user_content}
                        await current_subagent_ctx.__aexit__(None, None, None)
                        logger.info(f"[run_claude_agent_activity] 🤖 Completed subagent execution")
                        current_subagent_span = None
                        current_subagent_ctx = None

                    # Extract content
                    user_content = message.content
                    if isinstance(user_content, list):
                        # content might be list of blocks
                        user_content = str(user_content)

                    # Stream tool response
                    try:
                        async with adk.streaming.streaming_task_message_context(
                            task_id=task_id,
                            initial_content=ToolResponseContent(
                                author="agent",
                                name=tool_name,
                                content=user_content,
                                tool_call_id=last_tool_call_id,
                            )
                        ) as tool_ctx:
                            await tool_ctx.stream_update(
                                StreamTaskMessageFull(
                                    parent_task_message=tool_ctx.task_message,
                                    content=ToolResponseContent(
                                        author="agent",
                                        name=tool_name,
                                        content=user_content,
                                        tool_call_id=last_tool_call_id,
                                    ),
                                    type="full"
                                )
                            )
                    except Exception as e:
                        logger.warning(f"Failed to stream tool response: {e}")

                    # Clear the last tool call
                    last_tool_call_id = None

                # Stream different content types to UI
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        # Stream tool requests (Read, Write, Bash, etc.)
                        if isinstance(block, ToolUseBlock) and task_id:
                            logger.info(f"[run_claude_agent_activity] 🔧 [{msg_num}] STREAMING Tool request: {block.name}")

                            # Track tool_call_id → tool_name mapping for results
                            tool_call_map[block.id] = block.name
                            last_tool_call_id = block.id  # Remember for matching result

                            # Special handling for Task tool (subagents) - create nested span
                            if block.name == "Task" and trace_id and parent_span_id:
                                subagent_type = block.input.get("subagent_type", "unknown")
                                logger.info(f"[run_claude_agent_activity] 🤖 Starting subagent: {subagent_type}")

                                # Create nested trace span for subagent execution
                                current_subagent_ctx = adk.tracing.span(
                                    trace_id=trace_id,
                                    parent_id=parent_span_id,
                                    name=f"Subagent: {subagent_type}",
                                    input=block.input,
                                )
                                current_subagent_span = await current_subagent_ctx.__aenter__()

                            # Stream tool request directly (can't call activity from activity)
                            try:
                                async with adk.streaming.streaming_task_message_context(
                                    task_id=task_id,
                                    initial_content=ToolRequestContent(
                                        author="agent",
                                        name=block.name,
                                        arguments=block.input,
                                        tool_call_id=block.id,
                                    )
                                ) as tool_ctx:
                                    await tool_ctx.stream_update(
                                        StreamTaskMessageFull(
                                            parent_task_message=tool_ctx.task_message,
                                            content=ToolRequestContent(
                                                author="agent",
                                                name=block.name,
                                                arguments=block.input,
                                                tool_call_id=block.id,
                                            ),
                                            type="full"
                                        )
                                    )
                            except Exception as e:
                                logger.warning(f"Failed to stream tool request: {e}")

                        # Stream tool results
                        elif isinstance(block, ToolResultBlock) and task_id:
                            # Look up tool name from our mapping
                            tool_name = tool_call_map.get(block.tool_use_id, "unknown")
                            logger.info(f"[run_claude_agent_activity] ✅ Tool result: {tool_name}")

                            # Extract content from tool result
                            tool_content = block.content
                            if tool_content is None:
                                tool_content = ""

                            # Stream tool response directly (can't call activity from activity)
                            try:
                                async with adk.streaming.streaming_task_message_context(
                                    task_id=task_id,
                                    initial_content=ToolResponseContent(
                                        author="agent",
                                        name=tool_name,
                                        content=tool_content,
                                        tool_call_id=block.tool_use_id,
                                    )
                                ) as tool_ctx:
                                    await tool_ctx.stream_update(
                                        StreamTaskMessageFull(
                                            parent_task_message=tool_ctx.task_message,
                                            content=ToolResponseContent(
                                                author="agent",
                                                name=tool_name,
                                                content=tool_content,
                                                tool_call_id=block.tool_use_id,
                                            ),
                                            type="full"
                                        )
                                    )
                            except Exception as e:
                                logger.warning(f"Failed to stream tool response: {e}")

                        # Stream text blocks
                        elif isinstance(block, TextBlock) and block.text and streaming_ctx:
                            logger.info(f"[run_claude_agent_activity] 💬 [{msg_num}] STREAMING Text: {block.text[:50]}...")

                            # Create text delta
                            delta = TextDelta(
                                type="text",
                                text_delta=block.text
                            )

                            # Stream to UI
                            await streaming_ctx.stream_update(
                                StreamTaskMessageDelta(
                                    parent_task_message=streaming_ctx.task_message,
                                    delta=delta,
                                    type="delta"
                                )
                            )

        # Close streaming context
        if streaming_ctx:
            await streaming_ctx.close()
            logger.info(f"[run_claude_agent_activity] Closed streaming context")

    except Exception as e:
        logger.error(f"[run_claude_agent_activity] Error: {e}", exc_info=True)
        if streaming_ctx:
            try:
                await streaming_ctx.close()
            except:
                pass
        raise

    logger.info(f"[run_claude_agent_activity] Completed - collected {len(messages)} messages")

    # Parse and serialize messages for Temporal
    serialized_messages = []
    usage_info = None
    cost_info = None
    session_id = resume_session_id  # Start with resume_session_id, update if we get a new one

    for msg in messages:
        if isinstance(msg, SystemMessage):
            # Extract session_id from init message
            if msg.subtype == "init":
                session_id = msg.data.get("session_id")
                logger.info(
                    f"[run_claude_agent_activity] Session: "
                    f"{'STARTED' if not resume_session_id else 'CONTINUED'} ({session_id[:16] if session_id else 'unknown'}...)"
                )
            # Skip system messages in output (just metadata)
            logger.debug(f"[run_claude_agent_activity] SystemMessage: {msg.subtype}")
            continue

        if isinstance(msg, AssistantMessage):
            # Extract text from assistant messages
            text_content = []
            for block in msg.content:
                if isinstance(block, TextBlock):
                    text_content.append(block.text)

            if text_content:
                serialized_messages.append({
                    "role": "assistant",
                    "content": "\n".join(text_content)
                })

        elif isinstance(msg, ResultMessage):
            # Extract usage and cost info
            usage_info = msg.usage
            cost_info = msg.total_cost_usd
            # Update session_id from result message if available
            if msg.session_id:
                session_id = msg.session_id
            logger.info(
                f"[run_claude_agent_activity] Result - "
                f"cost=${cost_info:.4f}, duration={msg.duration_ms}ms, turns={msg.num_turns}"
            )

    return {
        "messages": serialized_messages,
        "task_id": task_id,
        "session_id": session_id,  # Return session_id for next turn!
        "usage": usage_info,
        "cost_usd": cost_info,
    }


__all__ = [
    "run_claude_agent_activity",
    "ContextInterceptor",  # Reuse from OpenAI - no changes needed!
    "streaming_task_id",
    "streaming_trace_id",
    "streaming_parent_span_id",
]
