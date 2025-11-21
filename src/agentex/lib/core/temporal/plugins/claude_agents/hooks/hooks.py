"""Claude SDK hooks for streaming tool calls and subagent execution to AgentEx UI.

This module provides hook callbacks that integrate with Claude SDK's hooks system
to stream tool execution lifecycle events in real-time.
"""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import HookMatcher

from agentex.lib import adk
from agentex.lib.utils.logging import make_logger
from agentex.types.task_message_update import StreamTaskMessageFull
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent

logger = make_logger(__name__)


class TemporalStreamingHooks:
    """Hooks for streaming Claude SDK lifecycle events to AgentEx UI.

    Implements Claude SDK hook callbacks:
    - PreToolUse: Called before tool execution → stream tool request
    - PostToolUse: Called after tool execution → stream tool result

    Also handles subagent detection and nested tracing.
    """

    def __init__(
        self,
        task_id: str | None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ):
        """Initialize streaming hooks.

        Args:
            task_id: AgentEx task ID for routing streams
            trace_id: Trace ID for nested spans
            parent_span_id: Parent span ID for subagent spans
        """
        self.task_id = task_id
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id

        # Track active subagent spans
        self.subagent_spans: dict[str, Any] = {}  # tool_call_id → (ctx, span)

    async def pre_tool_use(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        _context: Any,
    ) -> dict[str, Any]:
        """Hook called before tool execution.

        Args:
            input_data: Contains tool_name, tool_input from Claude SDK
            tool_use_id: Unique ID for this tool call
            context: Hook context from Claude SDK

        Returns:
            Empty dict (allow execution to proceed)
        """
        if not self.task_id or not tool_use_id:
            return {}

        tool_name = input_data.get("tool_name", "unknown")
        tool_input = input_data.get("tool_input", {})

        logger.info(f"🔧 Tool request: {tool_name}")

        # Special handling for Task tool (subagents) - create nested span
        if tool_name == "Task" and self.trace_id and self.parent_span_id:
            subagent_type = tool_input.get("subagent_type", "unknown")
            logger.info(f"🤖 Subagent started: {subagent_type}")

            # Create nested trace span for subagent
            subagent_ctx = adk.tracing.span(
                trace_id=self.trace_id,
                parent_id=self.parent_span_id,
                name=f"Subagent: {subagent_type}",
                input=tool_input,
            )
            subagent_span = await subagent_ctx.__aenter__()
            self.subagent_spans[tool_use_id] = (subagent_ctx, subagent_span)

        # Stream tool request to UI
        try:
            async with adk.streaming.streaming_task_message_context(
                task_id=self.task_id,
                initial_content=ToolRequestContent(
                    author="agent",
                    name=tool_name,
                    arguments=tool_input,
                    tool_call_id=tool_use_id,
                )
            ) as tool_ctx:
                await tool_ctx.stream_update(
                    StreamTaskMessageFull(
                        parent_task_message=tool_ctx.task_message,
                        content=ToolRequestContent(
                            author="agent",
                            name=tool_name,
                            arguments=tool_input,
                            tool_call_id=tool_use_id,
                        ),
                        type="full"
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to stream tool request: {e}")

        return {}  # Allow execution

    async def post_tool_use(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        _context: Any,
    ) -> dict[str, Any]:
        """Hook called after tool execution.

        Args:
            input_data: Contains tool_name, tool_output from Claude SDK
            tool_use_id: Unique ID for this tool call
            context: Hook context from Claude SDK

        Returns:
            Empty dict
        """
        if not self.task_id or not tool_use_id:
            return {}

        tool_name = input_data.get("tool_name", "unknown")
        tool_output = input_data.get("tool_output", "")

        logger.info(f"✅ Tool result: {tool_name}")

        # If this was a subagent, close the nested span
        if tool_use_id in self.subagent_spans:
            subagent_ctx, subagent_span = self.subagent_spans[tool_use_id]
            subagent_span.output = {"result": tool_output}
            await subagent_ctx.__aexit__(None, None, None)
            logger.info(f"🤖 Subagent completed: {tool_name}")
            del self.subagent_spans[tool_use_id]

        # Stream tool response to UI
        try:
            async with adk.streaming.streaming_task_message_context(
                task_id=self.task_id,
                initial_content=ToolResponseContent(
                    author="agent",
                    name=tool_name,
                    content=tool_output,
                    tool_call_id=tool_use_id,
                )
            ) as tool_ctx:
                await tool_ctx.stream_update(
                    StreamTaskMessageFull(
                        parent_task_message=tool_ctx.task_message,
                        content=ToolResponseContent(
                            author="agent",
                            name=tool_name,
                            content=tool_output,
                            tool_call_id=tool_use_id,
                        ),
                        type="full"
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to stream tool response: {e}")

        return {}


def create_streaming_hooks(
    task_id: str | None,
    trace_id: str | None = None,
    parent_span_id: str | None = None,
) -> dict[str, list[HookMatcher]]:
    """Create Claude SDK hooks configuration for streaming.

    Returns hooks dict suitable for ClaudeAgentOptions(hooks=...).

    Args:
        task_id: AgentEx task ID for streaming
        trace_id: Trace ID for nested spans
        parent_span_id: Parent span ID for subagent spans

    Returns:
        Dict with PreToolUse and PostToolUse hook configurations
    """
    hooks_instance = TemporalStreamingHooks(task_id, trace_id, parent_span_id)

    return {
        "PreToolUse": [
            HookMatcher(
                matcher=None,  # Match all tools
                hooks=[hooks_instance.pre_tool_use]
            )
        ],
        "PostToolUse": [
            HookMatcher(
                matcher=None,  # Match all tools
                hooks=[hooks_instance.post_tool_use]
            )
        ],
    }
