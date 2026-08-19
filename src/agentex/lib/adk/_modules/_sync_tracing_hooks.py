"""Tool-call tracing for the sync (non-Temporal) OpenAI Agents path.

The sync path only spans `Model.stream_response`, the inference call.
The ``Runner`` executes tools *outside* that call, so tool time lands in gaps
between spans and no span accounts for it. Measured on dev-sgp, an agent whose
tools are slow reported a third of its real wall-clock time.

The Temporal plugin already solves this with ``TemporalStreamingHooks``. This is
the same span lifecycle without the Temporal activity plumbing, so both paths
produce the same trace shape.
"""

from __future__ import annotations

from typing import Any
from datetime import timedelta

from agents import Tool, Agent, RunHooks
from agents.run_context import RunContextWrapper

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

_TRACE_TIMEOUT = timedelta(seconds=5)
# Cap tool-result span output so a large payload can't bloat the trace.
_MAX_SPAN_OUTPUT_CHARS = 2000


def _get_adk() -> Any:
    """Lazily import the adk facade so this module stays cheap to import."""
    from agentex.lib import adk

    return adk


class SyncTracingHooks(RunHooks):
    """Opens one span per tool call, closed when the tool returns.

    Span width is therefore the tool's real execution time, which is the whole
    point: a duration recorded as an attribute on a zero-width span is invisible
    on a timeline.

    Every tracing call is best-effort. A tracing failure must never break a turn.
    """

    def __init__(
        self,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        task_id: str | None = None,
    ) -> None:
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        self.task_id = task_id
        # tool_call_id -> open span, so on_tool_end closes the right one.
        self._tool_spans: dict[str, Any] = {}

    @staticmethod
    def _tool_call_id(context: RunContextWrapper, tool: Tool) -> str:
        return getattr(context, "tool_call_id", None) or tool.name

    @staticmethod
    def _tool_arguments(context: RunContextWrapper) -> dict[str, Any]:
        raw = getattr(context, "tool_arguments", None)
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str) and raw:
            import json

            try:
                parsed = json.loads(raw)
            except ValueError:
                return {"raw": raw[:_MAX_SPAN_OUTPUT_CHARS]}
            return parsed if isinstance(parsed, dict) else {"raw": parsed}
        return {}

    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool) -> None:  # noqa: ARG002
        if not self.trace_id:
            return
        try:
            span = await _get_adk().tracing.start_span(
                trace_id=self.trace_id,
                parent_id=self.parent_span_id,
                task_id=self.task_id,
                name=tool.name,
                input={"arguments": self._tool_arguments(context)},
                start_to_close_timeout=_TRACE_TIMEOUT,
            )
            if span is not None:
                self._tool_spans[self._tool_call_id(context, tool)] = span
        except Exception as e:  # noqa: BLE001 - tracing is best-effort
            logger.warning(f"[tracing] tool start_span failed (non-fatal): {e}")

    async def on_tool_end(
        self,
        context: RunContextWrapper,
        agent: Agent,  # noqa: ARG002
        tool: Tool,
        result: str,
    ) -> None:
        span = self._tool_spans.pop(self._tool_call_id(context, tool), None)
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
        """Drain spans whose ``on_tool_end`` never fired.

        A runner that dies mid-tool (max-turns, cancellation, an SDK error) never
        fires the matching end hook, which would orphan the span. Call this from a
        ``finally`` around the run.
        """
        if not self._tool_spans:
            return
        orphaned = list(self._tool_spans.items())
        self._tool_spans.clear()
        for tool_call_id, span in orphaned:
            logger.warning(
                f"[tracing] tool span for {tool_call_id} left open "
                "(on_tool_end never fired); closing as incomplete"
            )
            try:
                span.output = {"result": None, "incomplete": True}
                await _get_adk().tracing.end_span(
                    trace_id=self.trace_id,
                    span=span,
                    start_to_close_timeout=_TRACE_TIMEOUT,
                )
            except Exception as e:  # noqa: BLE001 - tracing is best-effort
                logger.warning(f"[tracing] draining tool span failed (non-fatal): {e}")
