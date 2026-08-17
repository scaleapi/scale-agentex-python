"""Dedicated per-business-span observability wrapper span — DELEGATED to sgp_obs.

The span/id mechanics that used to live here (``_open_otel_span`` /
``_open_ddtrace_span`` / ``_tag_*_ambient`` / ``_hex_ids``) now live in
``sgp_obs.traces.backends`` behind the ``ObsBackend`` port, and the
wrapper-vs-ambient DECISION lives in ``sgp_obs.traces.Correlator``. This module
keeps the SDK's public surface (``ObsSpanHandle`` / ``open_obs_span`` /
``close_obs_span`` / ``tag_ambient_obs_span``) as thin adapters so callers and
tests are unchanged, and adds :func:`begin_obs` which ``trace.py`` uses to
delegate the whole decision in one call.

Reverse-tag source is ``agentex`` (this is the agentex SDK). Never raises.
"""

from __future__ import annotations

from typing import Dict, Optional

from sgp_obs.traces import SpanError, Correlator, BusinessRef, SpanRequest, BusinessSource, temporal as _sgp_temporal
from sgp_obs.traces.ports import ObsSpanHandle as _SgpHandle

from agentex.lib.core.tracing.obs_ids import LGTM, _OTEL, _DDTRACE, obs_mode, get_obs_mode

__all__ = (
    "ObsSpanHandle",
    "open_obs_span",
    "close_obs_span",
    "tag_ambient_obs_span",
    "begin_obs",
)


def _to_span_error(error: Optional[Dict[str, str]]) -> Optional[SpanError]:
    """SDK error dict ``{"type","message"}`` -> sgp_obs SpanError."""
    if not error:
        return None
    return SpanError(type=error.get("type"), message=error.get("message"))


def _biz(span_id: Optional[str], trace_id: Optional[str]) -> BusinessRef:
    # source=agentex: this SDK is the agentex business source; the reverse tag is
    # therefore ``agentex.business_span_id`` / ``agentex.business_trace_id``.
    return BusinessRef(trace_id=trace_id, span_id=span_id or "", source=BusinessSource.AGENTEX)


def _backend():
    """The backend for the current SGP_OBS_MODE (lgtm -> OTel, else ddtrace)."""
    return _OTEL if get_obs_mode() == LGTM else _DDTRACE


class ObsSpanHandle:
    """Live handle for an open wrapper span. Adapts a sgp_obs ``ObsSpanHandle`` to
    the SDK's shape: ``.correlation`` is the ``{obs_trace_id, obs_span_id}`` dict,
    and ``close(error)`` takes the SDK's ``{"type","message"}`` error dict."""

    __slots__ = ("correlation", "_inner")

    def __init__(self, inner: _SgpHandle) -> None:
        self._inner = inner
        self.correlation: Dict[str, str] = inner.correlation.as_metadata()

    def close(self, error: Optional[Dict[str, str]] = None) -> None:
        self._inner.close(_to_span_error(error))


def open_obs_span(
    name: str,
    business_span_id: Optional[str] = None,
    business_trace_id: Optional[str] = None,
) -> Optional[ObsSpanHandle]:
    """Open a step-named wrapper span in the active backend and make it active;
    ``None`` when there's no live context (caller falls back to ambient ids).
    Delegates to the sgp_obs backend. Never raises."""
    try:
        inner = _backend().open_span(name, _biz(business_span_id, business_trace_id))
    except Exception:  # pragma: no cover - backstop; obs must never break a call
        return None
    return ObsSpanHandle(inner) if inner is not None else None


def tag_ambient_obs_span(
    business_span_id: Optional[str] = None,
    business_trace_id: Optional[str] = None,
    prefer_otel: bool = False,
) -> None:
    """Stamp the reverse tag onto the CURRENTLY ACTIVE span without opening one.
    ``prefer_otel`` tags OTel first (the Temporal interceptor span is OTel
    regardless of SGP_OBS_MODE). Best-effort; never raises."""
    biz = _biz(business_span_id, business_trace_id)
    try:
        if prefer_otel:
            if _OTEL.tag_ambient(biz):
                return
            _DDTRACE.tag_ambient(biz)
            return
        _backend().tag_ambient(biz)
    except Exception:  # pragma: no cover - best-effort
        pass


def close_obs_span(handle: Optional[ObsSpanHandle], error: Optional[Dict[str, str]] = None) -> None:
    """Close the wrapper span, marking it errored when ``error`` is given. Safe on None."""
    if handle is None:
        return
    try:
        handle.close(error)
    except Exception:  # pragma: no cover - best-effort
        pass


def begin_obs(
    name: str,
    span_id: str,
    trace_id: Optional[str],
) -> tuple[Optional[ObsSpanHandle], Dict[str, str]]:
    """Delegate the ENTIRE wrapper-vs-ambient + backend decision to the sgp_obs
    ``Correlator`` and return the SDK-shaped ``(handle | None, {obs_trace_id,
    obs_span_id})``. Inside the dispatched start-span/end-span pair the Correlator
    tags the ambient span (no wrapper); elsewhere it opens a per-step wrapper.

    A fresh Correlator per call keeps the SDK's per-call ``SGP_OBS_MODE`` reading
    (the backends are stateless singletons; only the one-shot drift log resets).
    """
    req = SpanRequest(
        name=name,
        business=_biz(span_id, trace_id),
        in_activity=_sgp_temporal.in_activity(),
        is_dispatch_boundary=_sgp_temporal.in_dispatch_boundary(),
    )
    try:
        inner, edge = Correlator(_OTEL, _DDTRACE, obs_mode()).begin(req)
    except Exception:  # pragma: no cover - obs must never break the business span
        return None, {}
    return (ObsSpanHandle(inner) if inner is not None else None), edge.as_metadata()
