"""Adapter from SpanSignals to adk.tracing spans (best-effort, overridable)."""

from __future__ import annotations

from typing import Any

from agentex.lib.core.harness.types import OpenSpan, CloseSpan, SpanSignal

try:
    from agentex.lib.core.tracing.lineage import resolve_refs, merge_refs_into_data
except Exception:  # keep the harness importable without optional tracing deps

    def resolve_refs(tool_name: str, arguments: dict[str, Any] | None) -> list[dict[str, Any]]:  # noqa: ARG001
        return []

    def merge_refs_into_data(data: dict[str, Any] | None, refs: list[dict[str, Any]]) -> dict[str, Any]:  # noqa: ARG001
        return dict(data or {})


try:
    from agentex.lib.utils.logging import make_logger

    logger = make_logger(__name__)
except Exception:  # ddtrace may be absent in some envs; fall back to stdlib
    import logging

    logger = logging.getLogger(__name__)


def _as_span_payload(value: Any, *, key: str) -> Any:
    """Coerce a span input/output payload into a dict.

    The SGP spans API requires ``input`` and ``output`` to be objects: a scalar
    or string is rejected with a 422 and the span is dropped by the async
    processor. The SpanDeriver legitimately produces non-dict payloads — the
    reasoning span's output is the chain-of-thought string, and some harnesses'
    tool results are plain strings — so wrap anything that isn't already a dict
    (``None`` passes through unchanged so an absent payload stays absent).
    """
    if value is None or isinstance(value, dict):
        return value
    return {key: value}


class SpanTracer:
    """Opens/closes adk.tracing child spans in response to span signals.

    `tracing` defaults to the real `adk.tracing` module; inject a fake in tests
    or a custom tracer to override. No-op when `trace_id` is falsy. Never raises.

    The real TracingModule.end_span does NOT accept an output kwarg — output is
    recorded by mutating span.output before calling end_span, matching the pattern
    used throughout the codebase.

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
                    input=_as_span_payload(signal.input, key="input"),
                    parent_id=self.parent_span_id,
                    task_id=self.task_id,
                )
                if span is not None:
                    if signal.kind == "tool":
                        refs = resolve_refs(signal.name, signal.input if isinstance(signal.input, dict) else {})
                        if refs:
                            data = span.data if isinstance(span.data, dict) else {}
                            span.data = merge_refs_into_data(data, refs)
                    self._open[signal.key] = span
            elif isinstance(signal, CloseSpan):
                span = self._open.pop(signal.key, None)
                if span is not None:
                    # Output is recorded by mutating span.output before end_span.
                    # The real TracingModule.end_span signature is:
                    #   end_span(trace_id, span, start_to_close_timeout, heartbeat_timeout, retry_policy)
                    # It does not accept an output= kwarg.
                    span.output = _as_span_payload(signal.output, key="output")
                    # Tool failure status (ToolResponseContent.is_error) is recorded
                    # on span.data when the harness reports one; Span has no dedicated
                    # error field. None means no status was reported, so leave data alone.
                    if signal.is_error is not None:
                        data = span.data if isinstance(span.data, dict) else {}
                        span.data = {**data, "is_error": signal.is_error}
                    await self._tracing.end_span(
                        trace_id=self.trace_id,
                        span=span,
                    )
        except Exception as exc:  # best-effort: tracing never breaks delivery
            logger.warning("[harness.tracer] span signal failed: %s", exc)
