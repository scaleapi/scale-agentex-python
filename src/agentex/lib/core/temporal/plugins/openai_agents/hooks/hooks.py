"""Temporal streaming hooks for OpenAI Agents SDK lifecycle events.

This module provides a convenience class for streaming agent lifecycle events
to the AgentEx UI via Temporal activities, and (optionally) tracing tool calls
to SGP with both inputs and outputs.

Two responsibilities, independently switchable:

1. UI message emission (``emit_messages``, default True): streams
   ToolRequestContent / ToolResponseContent / handoff messages. Leave it on for
   the non-streaming model provider, which does not emit these itself. Turn it
   OFF when pairing with ``TemporalStreamingModelProvider`` — that model already
   streams the tool-call message from the model output, so emitting here as well
   double-posts every tool call. ``run_turn`` wires this off for you.

2. SGP tracing (enabled when ``trace_id`` is provided): opens a ``tool:<name>``
   span on tool start with the tool ARGUMENTS as its input and closes it on tool
   end with the result as its output, parented to ``parent_span_id``. Token usage
   metrics are always emitted via ``LLMMetricsHooks`` regardless of these flags.
"""
from __future__ import annotations

import json
import logging
from typing import Any, override
from datetime import timedelta

from agents import Tool, Agent, RunContextWrapper
from temporalio import workflow
from agents.tool_context import ToolContext

from agentex.types.text_content import TextContent
from agentex.types.task_message_content import ToolRequestContent, ToolResponseContent
from agentex.lib.core.observability.llm_metrics_hooks import LLMMetricsHooks
from agentex.lib.core.temporal.plugins.openai_agents.hooks.activities import stream_lifecycle_content

logger = logging.getLogger(__name__)

# Best-effort tracing budget — a tracing outage must never break a tool call.
_TRACE_TIMEOUT = timedelta(seconds=5)
# Cap tool-result span output so a large payload can't bloat the trace.
_MAX_SPAN_OUTPUT_CHARS = 2000


def _get_adk() -> Any:
    """Lazily import the adk facade for workflow-safe tracing.

    Kept lazy (not a module-level import) so this core hooks module does not pull
    the full adk surface — and its optional deps — at import time. Only invoked
    when a tool span is actually created (i.e. when ``trace_id`` is set).
    """
    from agentex.lib import adk

    return adk


class TemporalStreamingHooks(LLMMetricsHooks):
    """Convenience hooks class for streaming OpenAI Agent lifecycle events to the AgentEx UI.

    This class automatically streams agent lifecycle events (tool calls, handoffs) to the
    AgentEx UI via Temporal activities. It subclasses the OpenAI Agents SDK's RunHooks
    to intercept lifecycle events and forward them for real-time UI updates.

    Lifecycle events streamed (when ``emit_messages`` is True):
        - Tool requests (on_tool_start): Streams when a tool is about to be invoked
        - Tool responses (on_tool_end): Streams the tool's execution result
        - Agent handoffs (on_handoff): Streams when control transfers between agents

    Tracing (when ``trace_id`` is provided):
        - A ``tool:<name>`` SGP span per tool call, with the tool arguments as the
          span input and the tool result as the span output.

    Usage:
        Basic usage - streams all lifecycle events::

            from agentex.lib.core.temporal.plugins.openai_agents import TemporalStreamingHooks

            hooks = TemporalStreamingHooks(task_id="abc123")
            result = await Runner.run(agent, input, hooks=hooks)

        Paired with the streaming model provider (avoid double-posting tool
        messages — the model already streams them). Prefer ``run_turn`` which
        wires this for you::

            hooks = TemporalStreamingHooks(
                task_id="abc123",
                emit_messages=False,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

        Advanced - subclass for custom behavior::

            class MyCustomHooks(TemporalStreamingHooks):
                async def on_tool_start(self, context, agent, tool):
                    # Add custom logic before streaming
                    await self.my_custom_logging(tool)
                    # Call parent to stream to UI
                    await super().on_tool_start(context, agent, tool)

                async def on_agent_start(self, context, agent):
                    # Override empty methods for additional tracking
                    print(f"Agent {agent.name} started")

    Power users can ignore this class and subclass agents.RunHooks directly for full control.

    Note:
        Tool arguments are extracted from the ToolContext's tool_arguments field,
        which contains a JSON string of the arguments passed to the tool.

    Attributes:
        task_id: The AgentEx task ID for routing streamed events
        timeout: Timeout for streaming activity calls (default: 10 seconds)
        emit_messages: Whether to stream tool/handoff messages to the UI
        trace_id: When set, tool calls are traced to SGP (input + output)
        parent_span_id: Parent span for the per-tool spans
    """

    def __init__(
        self,
        task_id: str,
        timeout: timedelta = timedelta(seconds=10),
        *,
        emit_messages: bool = True,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ):
        """Initialize the streaming hooks.

        Args:
            task_id: AgentEx task ID for routing streamed events to the correct UI session
            timeout: Timeout for streaming activity invocations (default: 10 seconds)
            emit_messages: When True (default) stream tool/handoff messages to the
                UI. Set False when a streaming model provider already emits the
                tool-call messages, to avoid double-posting.
            trace_id: When provided, open a ``tool:<name>`` SGP span per tool call
                with the arguments as input and the result as output. When None,
                no tool spans are created (token-usage metrics still emit).
            parent_span_id: Parent span id the per-tool spans attach to.
        """
        super().__init__()
        self.task_id = task_id
        self.timeout = timeout
        self.emit_messages = emit_messages
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        # tool_call_id -> open SGP span, so on_tool_end closes the right one.
        self._tool_spans: dict[str, Any] = {}

    @staticmethod
    def _tool_call_id(context: RunContextWrapper, tool: Tool) -> str:
        tool_context = context if isinstance(context, ToolContext) else None
        return getattr(tool_context, "tool_call_id", None) or f"call_{id(tool)}"

    @staticmethod
    def _parse_tool_arguments(context: RunContextWrapper) -> dict[str, Any]:
        """Parse the JSON ``tool_arguments`` off a ToolContext into a dict.

        Returns an empty dict for a non-ToolContext or unparseable arguments —
        a tool call must never fail because its args could not be displayed.
        """
        tool_context = context if isinstance(context, ToolContext) else None
        raw = getattr(tool_context, "tool_arguments", None)
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Failed to parse tool arguments: {raw!r}")
            return {}
        return parsed if isinstance(parsed, dict) else {"value": parsed}

    @override
    async def on_agent_start(self, context: RunContextWrapper, agent: Agent) -> None:  # noqa: ARG002
        """Called when an agent starts execution.

        Default implementation logs the event. Override to add custom behavior.

        Args:
            context: The run context wrapper
            agent: The agent that is starting
        """
        logger.debug(f"[TemporalStreamingHooks] Agent '{agent.name}' started execution")

    @override
    async def on_agent_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:  # noqa: ARG002
        """Called when an agent completes execution.

        Default implementation logs the event. Override to add custom behavior.

        Args:
            context: The run context wrapper
            agent: The agent that completed
            output: The agent's output
        """
        logger.debug(
            f"[TemporalStreamingHooks] Agent '{agent.name}' completed execution with output type: {type(output).__name__}"
        )

    @override
    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool) -> None:  # noqa: ARG002
        """Stream the tool request (optional) and open a traced span (optional).

        Streams a ToolRequestContent message when ``emit_messages`` is True, and
        opens a ``tool:<name>`` SGP span (input = arguments) when ``trace_id`` is
        set. Both read the same parsed arguments.

        Args:
            context: The run context wrapper (a ToolContext with tool_call_id and tool_arguments)
            agent: The agent executing the tool
            tool: The tool being executed
        """
        tool_call_id = self._tool_call_id(context, tool)
        tool_arguments = self._parse_tool_arguments(context)

        if self.emit_messages:
            await workflow.execute_activity(
                stream_lifecycle_content,
                args=[
                    self.task_id,
                    ToolRequestContent(
                        author="agent",
                        tool_call_id=tool_call_id,
                        name=tool.name,
                        arguments=tool_arguments,
                    ).model_dump(),
                ],
                start_to_close_timeout=self.timeout,
            )

        await self._maybe_start_tool_span(tool_call_id, tool.name, tool_arguments)

    @override
    async def on_tool_end(
        self,
        context: RunContextWrapper,
        agent: Agent,  # noqa: ARG002
        tool: Tool,
        result: str,
    ) -> None:
        """Stream the tool response (optional) and close the traced span (optional).

        Streams a ToolResponseContent message when ``emit_messages`` is True, and
        closes the matching ``tool:<name>`` span (output = result) when one was
        opened in on_tool_start.

        Args:
            context: The run context wrapper (a ToolContext with tool_call_id)
            agent: The agent that executed the tool
            tool: The tool that was executed
            result: The tool's execution result
        """
        tool_call_id = self._tool_call_id(context, tool)

        if self.emit_messages:
            await workflow.execute_activity(
                stream_lifecycle_content,
                args=[
                    self.task_id,
                    ToolResponseContent(
                        author="agent",
                        tool_call_id=tool_call_id,
                        name=tool.name,
                        content=result,
                    ).model_dump(),
                ],
                start_to_close_timeout=self.timeout,
            )

        await self._maybe_end_tool_span(tool_call_id, result)

    @override
    async def on_handoff(
        self,
        context: RunContextWrapper,
        from_agent: Agent,
        to_agent: Agent,  # noqa: ARG002
    ) -> None:
        """Stream handoff message when control transfers between agents.

        Sends a text message to the UI indicating that one agent is handing off
        to another agent. No-op when ``emit_messages`` is False.

        Args:
            context: The run context wrapper
            from_agent: The agent transferring control
            to_agent: The agent receiving control
        """
        if not self.emit_messages:
            return
        await workflow.execute_activity(
            stream_lifecycle_content,
            args=[
                self.task_id,
                TextContent(
                    author="agent",
                    content=f"Handoff from {from_agent.name} to {to_agent.name}",
                    type="text",
                ).model_dump(),
            ],
            start_to_close_timeout=self.timeout,
        )

    async def _maybe_start_tool_span(self, tool_call_id: str, tool_name: str, arguments: dict[str, Any]) -> None:
        """Open a ``tool:<name>`` SGP span with the arguments as input.

        Best-effort: tracing must never break a tool call, so any failure is
        logged and swallowed. No-op when ``trace_id`` is not set.
        """
        if not self.trace_id:
            return
        try:
            span = await _get_adk().tracing.start_span(
                trace_id=self.trace_id,
                parent_id=self.parent_span_id,
                name=f"tool:{tool_name}",
                input={"arguments": arguments},
                start_to_close_timeout=_TRACE_TIMEOUT,
            )
            if span is not None:
                self._tool_spans[tool_call_id] = span
        except Exception as e:  # noqa: BLE001 - tracing is best-effort
            logger.warning(f"[tracing] tool start_span failed (non-fatal): {e}")

    async def _maybe_end_tool_span(self, tool_call_id: str, result: Any) -> None:
        """Close the span opened for ``tool_call_id`` with the result as output."""
        span = self._tool_spans.pop(tool_call_id, None)
        if span is None or not self.trace_id:
            return
        try:
            span.output = {"result": str(result)[:_MAX_SPAN_OUTPUT_CHARS]}
            await _get_adk().tracing.end_span(
                trace_id=self.trace_id,
                span=span,
                start_to_close_timeout=_TRACE_TIMEOUT,
            )
        except Exception as e:  # noqa: BLE001 - tracing is best-effort
            logger.warning(f"[tracing] tool end_span failed (non-fatal): {e}")

    async def close_open_tool_spans(self) -> None:
        """Close any tool spans still open because ``on_tool_end`` never fired.

        ``on_tool_start`` opens a span that ``on_tool_end`` is expected to close.
        If the runner terminates mid-tool (max-turns exceeded, cancellation, an
        unexpected SDK exception), the matching ``on_tool_end`` never runs and the
        span would otherwise stay open forever — orphaned in the tracing backend.
        Call this from a ``finally`` around ``Runner.run`` to drain the leftovers.

        Best-effort, like the rest of tracing: each span is closed with an
        ``incomplete`` marker and any failure is logged and swallowed.
        """
        if not self._tool_spans:
            return
        orphaned = list(self._tool_spans.items())
        self._tool_spans.clear()
        for tool_call_id, span in orphaned:
            logger.warning(
                f"[tracing] tool span for {tool_call_id} left open (on_tool_end never fired); closing as incomplete"
            )
            try:
                span.output = {"result": None, "status": "incomplete"}
                await _get_adk().tracing.end_span(
                    trace_id=self.trace_id,
                    span=span,
                    start_to_close_timeout=_TRACE_TIMEOUT,
                )
            except Exception as e:  # noqa: BLE001 - tracing is best-effort
                logger.warning(f"[tracing] orphan tool end_span failed (non-fatal): {e}")
