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

from typing import Dict, Callable, Optional

from agentex.lib.core.tracing.obs_ids import LGTM, get_obs_mode

__all__ = ("ObsSpanHandle", "open_obs_span", "close_obs_span", "tag_ambient_obs_span")

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

    def close(self, error: Optional[Dict[str, str]] = None) -> None:
        """Run the backend-specific closer (detach+end for OTel, finish for
        ddtrace). ``error`` marks the obs span failed so it isn't a false green."""
        self._close(error)


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
        from opentelemetry import trace, context
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
        if not (sc and sc.is_valid):
            # No real TracerProvider installed (lgtm mode but the agent has no
            # OTel provider yet): the proxy tracer hands back a NonRecordingSpan
            # with an invalid context. Returning a handle with empty correlation
            # here would make the caller (trace.py) take obs_handle.correlation
            # == {} and NEVER consult the obs_correlation() ambient fallback --
            # so the business span would get no obs_* ids at all, strictly worse
            # than falling back. Detach the useless context, end the no-op span,
            # and return None so the caller uses the ambient ids instead.
            context.detach(token)
            span.end()
            return None
        correlation = _hex_ids(sc.trace_id, sc.span_id)

        def _close(error: Optional[Dict[str, str]] = None) -> None:
            try:
                if error:
                    # Reflect the business-step failure on the obs span so it
                    # isn't a false green when you pivot from a failed span.
                    span.set_status(trace.Status(trace.StatusCode.ERROR, error.get("message")))
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
        ctx = tracer.current_trace_context()
        if ctx is None:
            return None
        # child_of=ctx is load-bearing: ddtrace's start_span does NOT auto-parent
        # to the active span (unlike OTel), so start_span(name) alone mints a NEW
        # root trace every call -- scattering a turn's business spans across N
        # Datadog traces. Parenting to the active request/turn context rolls them
        # into one trace while obs_span_id stays distinct per step.
        span = tracer.start_span(name, child_of=ctx, activate=True)
        if not span.trace_id:
            # Symmetry with the OTel path: a handle carrying empty correlation
            # would suppress the ambient obs_correlation() fallback in trace.py.
            # (child_of=ctx normally guarantees a real trace_id, so this is
            # belt-and-braces.) Finish the span and fall back to ambient ids.
            span.finish()
            return None
        if business_span_id:
            span.set_tag(_ATTR_BUSINESS_SPAN_ID, business_span_id)
        if business_trace_id:
            span.set_tag(_ATTR_BUSINESS_TRACE_ID, business_trace_id)
        correlation = _hex_ids(span.trace_id, span.span_id)

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


def _tag_otel_ambient(business_span_id: Optional[str], business_trace_id: Optional[str]) -> bool:
    """Stamp the reverse tag onto the active OTel span. Returns True iff a valid
    OTel span was found and tagged."""
    try:
        from opentelemetry import trace
    except ImportError:
        return False
    span = trace.get_current_span()
    if span is not None and span.get_span_context().is_valid:
        if business_span_id:
            span.set_attribute(_ATTR_BUSINESS_SPAN_ID, business_span_id)
        if business_trace_id:
            span.set_attribute(_ATTR_BUSINESS_TRACE_ID, business_trace_id)
        return True
    return False


def _tag_ddtrace_ambient(business_span_id: Optional[str], business_trace_id: Optional[str]) -> bool:
    """Stamp the reverse tag onto the active ddtrace span. Returns True iff a
    ddtrace span was found and tagged."""
    try:
        from ddtrace.trace import tracer
    except ImportError:
        return False
    span = tracer.current_span()
    if span is not None:
        if business_span_id:
            span.set_tag(_ATTR_BUSINESS_SPAN_ID, business_span_id)
        if business_trace_id:
            span.set_tag(_ATTR_BUSINESS_TRACE_ID, business_trace_id)
        return True
    return False


def tag_ambient_obs_span(
    business_span_id: Optional[str] = None,
    business_trace_id: Optional[str] = None,
    prefer_otel: bool = False,
) -> None:
    """Stamp the reverse tag onto the CURRENTLY ACTIVE obs span -- without opening
    a new one.

    Used on the Temporal path (see ``trace._in_temporal_activity``): there we must
    NOT open our own wrapper span, because start_span/end_span run as separate
    activities on possibly different workers and the wrapper could never be
    closed. Instead we lean on the span the Temporal OTel ``TracingInterceptor``
    already made active for this activity and just add
    ``agentex.business_span_id`` / ``agentex.business_trace_id`` so the obs -> business
    pivot still works. Best-effort; never raises.

    ``prefer_otel``: on the Temporal path the ambient span is the temporalio OTel
    ``TracingInterceptor`` span REGARDLESS of ``SGP_OBS_MODE`` -- so callers there
    pass ``prefer_otel=True`` to tag OTel first (falling back to ddtrace only if
    no valid OTel span is active). Without this, the default ``dd_only`` mode would
    tag an unrelated ddtrace span (or nothing) instead of the real activity span."""
    try:
        if prefer_otel:
            if _tag_otel_ambient(business_span_id, business_trace_id):
                return
            _tag_ddtrace_ambient(business_span_id, business_trace_id)
            return
        if get_obs_mode() == LGTM:
            _tag_otel_ambient(business_span_id, business_trace_id)
        else:
            _tag_ddtrace_ambient(business_span_id, business_trace_id)
    except Exception:  # pragma: no cover - best-effort; obs must never break a call
        pass


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
        handle.close(error)
    except Exception:  # pragma: no cover - best-effort
        pass
