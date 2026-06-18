"""Adapter from SpanSignals to adk.tracing spans (best-effort, overridable)."""

from __future__ import annotations

from typing import Any

from agentex.lib.core.harness.types import CloseSpan, OpenSpan, SpanSignal

try:
    from agentex.lib.utils.logging import make_logger

    logger = make_logger(__name__)
except Exception:  # ddtrace may be absent in some envs; fall back to stdlib
    import logging

    logger = logging.getLogger(__name__)


class SpanTracer:
    """Opens/closes adk.tracing child spans in response to span signals.

    `tracing` defaults to the real `adk.tracing` module; inject a fake in tests
    or a custom tracer to override. No-op when `trace_id` is falsy. Never raises.

    The real TracingModule.end_span does NOT accept an output kwarg — output is
    recorded by mutating span.output before calling end_span, matching the pattern
    used throughout the codebase (see _langgraph_tracing.py on_tool_end etc.).

    Span-lifecycle contract: the `_open` dict (span key -> span object) is scoped
    to a single turn. Pairing is by `key`:
    - A duplicate OpenSpan for a key already in `_open` silently replaces the
      earlier span; the earlier span is then orphaned (never closed / leaked).
    - A CloseSpan for an unknown key is a no-op.
    - Unpaired opens accumulate in `_open` for the lifetime of the tracer; since
      a tracer is expected to live for one turn, this is bounded and acceptable.
    """

    def __init__(
        self,
        trace_id: str | None,
        parent_span_id: str | None,
        tracing: Any = None,
        task_id: str | None = None,
    ):
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        self.task_id = task_id
        if tracing is None:
            from agentex.lib import adk

            tracing = adk.tracing
        self._tracing = tracing
        self._open: dict[str, Any] = {}  # span key -> span object

    async def handle(self, signal: SpanSignal) -> None:
        if not self.trace_id:
            return
        try:
            if isinstance(signal, OpenSpan):
                span = await self._tracing.start_span(
                    trace_id=self.trace_id,
                    name=signal.name,
                    input=signal.input,
                    parent_id=self.parent_span_id,
                    task_id=self.task_id,
                )
                if span is not None:
                    self._open[signal.key] = span
            elif isinstance(signal, CloseSpan):
                span = self._open.pop(signal.key, None)
                if span is not None:
                    # Output is recorded by mutating span.output before end_span.
                    # The real TracingModule.end_span signature is:
                    #   end_span(trace_id, span, start_to_close_timeout, heartbeat_timeout, retry_policy)
                    # It does not accept an output= kwarg.
                    span.output = signal.output
                    await self._tracing.end_span(
                        trace_id=self.trace_id,
                        span=span,
                    )
        except Exception as exc:  # best-effort: tracing never breaks delivery
            logger.warning("[harness.tracer] span signal failed: %s", exc)
