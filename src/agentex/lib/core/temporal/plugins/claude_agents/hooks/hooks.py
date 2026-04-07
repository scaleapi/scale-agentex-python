"""Claude SDK hooks for streaming tool calls and subagent execution to AgentEx UI.

This module provides hook callbacks that integrate with Claude SDK's hooks system
to stream tool execution lifecycle events in real-time.

Hooks:
- PreToolUse (auto_allow): Auto-allows all tool permissions
- PostToolUse: Streams tool results to the AgentEx UI
- PostToolUseFailure: Streams tool errors to the AgentEx UI
"""

from __future__ import annotations

from typing import Any

from claude_agent_sdk.types import (
    HookEvent,
    HookInput,
    HookContext,
    HookMatcher,
    HookJSONOutput,
    SyncHookJSONOutput,
    PreToolUseHookSpecificOutput,
)

from agentex.lib import adk
from agentex.lib.utils.logging import make_logger
from agentex.types.task_message_update import StreamTaskMessageFull
from agentex.types.tool_response_content import ToolResponseContent

logger = make_logger(__name__)


class TemporalStreamingHooks:
    """Hooks for streaming Claude SDK lifecycle events to AgentEx UI.

    Implements Claude SDK hook callbacks:
    - PreToolUse: Auto-allow tool permissions
    - PostToolUse: Stream tool result to UI
    - PostToolUseFailure: Stream tool error to UI

    Also handles subagent span cleanup for nested tracing.
    """

    def __init__(
        self,
        task_id: str | None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        subagent_spans: dict[str, Any] | None = None,
    ):
        """Initialize streaming hooks.

        Args:
            task_id: AgentEx task ID for routing streams
            trace_id: Trace ID for nested spans
            parent_span_id: Parent span ID for subagent spans
            subagent_spans: Shared dict tracking active subagent spans
                (tool_use_id → (ctx, span)). Passed by reference from the
                activity so hooks and message-level streaming share state.
        """
        self.task_id = task_id
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        self.subagent_spans = subagent_spans if subagent_spans is not None else {}

    async def auto_allow_hook(
        self,
        _input_data: HookInput,
        _tool_use_id: str | None,
        _context: HookContext,
    ) -> HookJSONOutput:
        """Hook called before tool execution — auto-allows all tools."""
        return SyncHookJSONOutput(
            continue_=True,
            hookSpecificOutput=PreToolUseHookSpecificOutput(
                hookEventName="PreToolUse",
                permissionDecision="allow",
            ),
        )

    async def post_tool_use_hook(
        self,
        input_data: HookInput,
        _tool_use_id: str | None,
        _context: HookContext,
    ) -> HookJSONOutput:
        """Hook called after tool execution — streams tool result to UI."""
        _continue = SyncHookJSONOutput(continue_=True)
        if input_data["hook_event_name"] != "PostToolUse":
            return _continue

        tool_name = input_data["tool_name"]
        tool_use_id = input_data["tool_use_id"]
        tool_output = input_data.get("tool_response") or input_data.get("tool_output", "")  # type: ignore[arg-type]

        logger.info(f"Tool result: {tool_name}")

        # Close subagent span before the task_id guard — spans are opened
        # based on trace_id/parent_span_id, not task_id.
        if tool_use_id in self.subagent_spans:
            subagent_ctx, subagent_span = self.subagent_spans.pop(tool_use_id)
            subagent_span.output = {"result": tool_output}
            try:
                await subagent_ctx.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Failed to close subagent span: {e}")

        if not self.task_id:
            return _continue

        response_content = ToolResponseContent(
            author="agent",
            name=tool_name,
            content=tool_output,
            tool_call_id=tool_use_id,
        )
        try:
            async with adk.streaming.streaming_task_message_context(
                task_id=self.task_id,
                initial_content=response_content,
            ) as ctx:
                await ctx.stream_update(
                    StreamTaskMessageFull(
                        parent_task_message=ctx.task_message,
                        content=response_content,
                        type="full",
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to stream tool response: {e}")
        return _continue

    async def post_tool_use_failure_hook(
        self,
        input_data: HookInput,
        _tool_use_id: str | None,
        _context: HookContext,
    ) -> HookJSONOutput:
        """Hook called after tool failure — streams tool error to UI."""
        _continue = SyncHookJSONOutput(continue_=True)
        if input_data["hook_event_name"] != "PostToolUseFailure":
            return _continue

        tool_name = input_data["tool_name"]
        tool_use_id = input_data["tool_use_id"]
        error = input_data["error"]

        logger.warning(f"Tool failed: {tool_name} — {error}")

        # Close subagent span before the task_id guard — spans are opened
        # based on trace_id/parent_span_id, not task_id.
        if tool_use_id in self.subagent_spans:
            subagent_ctx, subagent_span = self.subagent_spans.pop(tool_use_id)
            subagent_span.output = {"error": error}
            try:
                await subagent_ctx.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Failed to close subagent span: {e}")

        if not self.task_id:
            return _continue

        response_content = ToolResponseContent(
            author="agent",
            name=tool_name,
            content=f"Error: {error}",
            tool_call_id=tool_use_id,
        )
        try:
            async with adk.streaming.streaming_task_message_context(
                task_id=self.task_id,
                initial_content=response_content,
            ) as ctx:
                await ctx.stream_update(
                    StreamTaskMessageFull(
                        parent_task_message=ctx.task_message,
                        content=response_content,
                        type="full",
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to stream tool failure: {e}")
        return _continue


def create_streaming_hooks(
    task_id: str | None,
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    subagent_spans: dict[str, Any] | None = None,
) -> dict[HookEvent, list[HookMatcher]]:
    """Create Claude SDK hooks configuration for streaming.

    Returns hooks dict suitable for ClaudeAgentOptions(hooks=...).

    Args:
        task_id: AgentEx task ID for streaming
        trace_id: Trace ID for nested spans
        parent_span_id: Parent span ID for subagent spans
        subagent_spans: Shared dict tracking active subagent spans

    Returns:
        Dict with PreToolUse, PostToolUse, and PostToolUseFailure hook configurations
    """
    hooks_instance = TemporalStreamingHooks(task_id, trace_id, parent_span_id, subagent_spans)

    return {
        "PreToolUse": [HookMatcher(matcher=None, hooks=[hooks_instance.auto_allow_hook])],
        "PostToolUse": [HookMatcher(matcher=None, hooks=[hooks_instance.post_tool_use_hook])],
        "PostToolUseFailure": [HookMatcher(matcher=None, hooks=[hooks_instance.post_tool_use_failure_hook])],
    }
