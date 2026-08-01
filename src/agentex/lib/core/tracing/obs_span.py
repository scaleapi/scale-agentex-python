"""Dedicated per-business-span observability wrapper span.

Capturing obs ids from "whatever instrumentation span happens to be innermost
at emit time" is coarse -- it could be an arbitrary httpx-client span, and every
business span in a request would collapse onto the same request/activity span.

Instead, when the SDK creates a business span we open a **real obs span named
for that step and make it active**. Then:
  - ``obs_span_id`` is stable and meaningful (a span named for the business
    step, not an arbitrary leaf), and
  - any nested instrumentation (httpx, db, ...) parents under it.

The wrapper's own trace_id/span_id are read directly from its span context, so
the correlation tag is deterministic regardless of what else is on the stack.

Backend follows ``SGP_OBS_MODE``:
  - ``lgtm``    -> an OpenTelemetry span (the convergence target).
  - ``dd_only`` -> a ddtrace span, but ONLY when a ddtrace trace is already
    active for the request. Opening one unconditionally would emit orphan root
    traces in un-instrumented (bare-uvicorn, no ddtrace-run) agents, so when
    nothing is active we return ``None`` and the caller keeps its ambient
    behavior.

No-op when the relevant tracer isn't importable. Never raises -- observability
must never break a business span.
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

from agentex.lib.core.tracing.obs_ids import LGTM, get_obs_mode

__all__ = ("ObsSpanHandle", "open_obs_span", "close_obs_span")

# Instrumentation scope name so these wrapper spans are identifiable in Tempo/DD.
_TRACER_NAME = "agentex.business"

# Reverse-tag attribute keys: the business span/trace ids stamped onto the obs
# span so you can pivot obs -> business (search these in Tempo/DD).
_ATTR_BUSINESS_SPAN_ID = "agentex.business_span_id"
_ATTR_BUSINESS_TRACE_ID = "agentex.business_trace_id"


class ObsSpanHandle:
    """Live handle for an open wrapper span: the correlation tag read from it
    plus a backend-specific closer (detach/end or finish)."""

    __slots__ = ("correlation", "_close")

    def __init__(
        self,
        correlation: Dict[str, str],
        close: Callable[[Optional[Dict[str, str]]], None],
    ):
        self.correlation = correlation
        self._close = close


def _hex_ids(trace_id: int, span_id: int) -> Dict[str, str]:
    """W3C-hex form: 32-hex trace, 16-hex span."""
    return {
        "obs_trace_id": format(trace_id, "032x"),
        "obs_span_id": format(span_id, "016x"),
    }


def _open_otel_span(
    name: str,
    business_span_id: Optional[str],
    business_trace_id: Optional[str],
) -> Optional[ObsSpanHandle]:
    try:
        from opentelemetry import context, trace
    except ImportError:
        return None
    try:
        span = trace.get_tracer(_TRACER_NAME).start_span(name)
        if business_span_id:
            span.set_attribute(_ATTR_BUSINESS_SPAN_ID, business_span_id)
        if business_trace_id:
            span.set_attribute(_ATTR_BUSINESS_TRACE_ID, business_trace_id)
        token = context.attach(trace.set_span_in_context(span))
        sc = span.get_span_context()
        correlation = _hex_ids(sc.trace_id, sc.span_id) if (sc and sc.is_valid) else {}

        def _close(error: Optional[Dict[str, str]] = None) -> None:
            try:
                if error:
                    # Reflect the business-step failure on the obs span so it
                    # isn't a false green when you pivot from a failed span.
                    span.set_status(
                        trace.Status(trace.StatusCode.ERROR, error.get("message"))
                    )
                    if error.get("type"):
                        span.set_attribute("error.type", error["type"])
            finally:
                try:
                    context.detach(token)
                finally:
                    span.end()

        return ObsSpanHandle(correlation, _close)
    except Exception:  # pragma: no cover - best-effort; never break the business span
        return None


def _open_ddtrace_span(
    name: str,
    business_span_id: Optional[str],
    business_trace_id: Optional[str],
) -> Optional[ObsSpanHandle]:
    try:
        from ddtrace.trace import tracer
    except ImportError:
        return None
    try:
        # Only wrap when ddtrace is actually tracing the request; otherwise a
        # wrapper would be an orphan root trace in an un-instrumented process.
        if tracer.current_trace_context() is None:
            return None
        span = tracer.start_span(name, activate=True)
        if business_span_id:
            span.set_tag(_ATTR_BUSINESS_SPAN_ID, business_span_id)
        if business_trace_id:
            span.set_tag(_ATTR_BUSINESS_TRACE_ID, business_trace_id)
        correlation = _hex_ids(span.trace_id, span.span_id) if span.trace_id else {}

        def _close(error: Optional[Dict[str, str]] = None) -> None:
            try:
                if error:
                    # Reflect the business-step failure on the obs span.
                    span.error = 1
                    if error.get("type"):
                        span.set_tag("error.type", error["type"])
                    if error.get("message"):
                        span.set_tag("error.message", error["message"])
            finally:
                span.finish()

        return ObsSpanHandle(correlation, _close)
    except Exception:  # pragma: no cover - best-effort
        return None


def open_obs_span(
    name: str,
    business_span_id: Optional[str] = None,
    business_trace_id: Optional[str] = None,
) -> Optional[ObsSpanHandle]:
    """Open an obs span named ``name`` in the active backend, make it the active
    span, and return a handle carrying its ``{"obs_trace_id","obs_span_id"}``.

    ``business_span_id`` / ``business_trace_id`` are stamped onto the obs span as
    the reverse tag (``agentex.business_span_id`` / ``agentex.business_trace_id``)
    so you can pivot obs -> business by searching them in Tempo/DD.

    Returns ``None`` (so the caller falls back to ambient behavior) when the
    backend tracer isn't available or, in ``dd_only``, no request trace is
    active.

    Never raises: a top-level guard backstops anything the backend helpers
    don't (e.g. a broken tracer install raising on import) so observability can
    never fail an app call.
    """
    try:
        if get_obs_mode() == LGTM:
            return _open_otel_span(name, business_span_id, business_trace_id)
        return _open_ddtrace_span(name, business_span_id, business_trace_id)
    except Exception:  # pragma: no cover - backstop; obs must never break a call
        return None


def close_obs_span(
    handle: Optional[ObsSpanHandle],
    error: Optional[Dict[str, str]] = None,
) -> None:
    """Close the wrapper span (detach + end, or finish). When ``error`` is given
    (the business span failed), mark the obs span errored first so it reflects
    failure rather than a false green. Safe on ``None``."""
    if handle is None:
        return
    try:
        handle._close(error)
    except Exception:  # pragma: no cover - best-effort
        pass
