"""Correlate adk business spans with the active observability trace.

The adk business ``trace_id`` is the agent **task id** (run-level: it spans the
whole agent run across many requests -- task/create, then each message/send turn),
so we must NOT overwrite it with a per-request observability trace_id. Doing so
would collapse the run-level grouping.

Instead, each business span is *tagged* with the active observability
trace_id/span_id (this is the OpenTelemetry "span link" pattern -- correlate
across trace granularities rather than merging them). You can then pivot from a
persisted business span to the Tempo/Datadog trace for the turn that produced it,
while the business trace still groups the entire run by task id.

Source selection follows SGP_OBS_MODE, matching egp-api-backend:
  - unset / "dd_only": ddtrace context (current stack)
  - "dual":            OTel/LGTM preferred, ddtrace fallback
  - "lgtm":            OTel/LGTM only

This never fabricates ids -- if no observability context is active, it returns
an empty dict and the span is simply not tagged.
"""
from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

__all__ = ("get_obs_mode", "obs_correlation", "sync_ddtrace_to_lgtm")

DD_ONLY = "dd_only"
DUAL = "dual"
LGTM = "lgtm"
_DEFAULT_MODE = DD_ONLY
_VALID_MODES = (DD_ONLY, DUAL, LGTM)


def get_obs_mode() -> str:
    """Unset/empty/unrecognized -> ``dd_only`` (current behavior)."""
    raw = os.getenv("SGP_OBS_MODE")
    if not raw:
        return _DEFAULT_MODE
    mode = raw.strip().lower()
    return mode if mode in _VALID_MODES else _DEFAULT_MODE


def _lgtm_ids() -> Optional[Tuple[str, str]]:
    try:
        from opentelemetry import trace
    except ImportError:
        return None
    ctx = trace.get_current_span().get_span_context()
    if ctx and ctx.is_valid:
        return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
    return None


def _ddtrace_ids() -> Optional[Tuple[str, str]]:
    try:
        from ddtrace import tracer
    except ImportError:
        return None
    ctx = tracer.current_trace_context()
    if ctx and ctx.trace_id:
        return format(ctx.trace_id, "032x"), format(ctx.span_id or 0, "016x")
    return None


def obs_correlation() -> Dict[str, str]:
    """Return ``{"obs.trace_id": ..., "obs.span_id": ...}`` for the active
    observability context, or ``{}`` if none is active.

    Never fabricates ids -- this is a correlation tag, not the span's id.
    """
    mode = get_obs_mode()
    if mode == LGTM:
        ids = _lgtm_ids()
    elif mode == DUAL:
        ids = _lgtm_ids() or _ddtrace_ids()
    else:  # dd_only
        ids = _ddtrace_ids()

    if not ids:
        return {}
    return {"obs.trace_id": ids[0], "obs.span_id": ids[1]}


def sync_ddtrace_to_lgtm() -> None:
    """In ``dual`` mode, make ddtrace adopt the active OpenTelemetry/LGTM trace
    context so ddtrace-emitted spans (best-effort Datadog) share the SAME
    trace_id as the OTel trace. Call at request ingress once the OTel span is
    active, and after any context boundary (e.g. entering a Temporal activity).

    No-op outside ``dual`` mode, or when OTel/ddtrace is unavailable or no OTel
    span is active. Never raises.
    """
    if get_obs_mode() != DUAL:
        return
    try:
        from opentelemetry import trace

        try:
            from ddtrace.trace import Context  # ddtrace 3.x
        except ImportError:  # pragma: no cover - older ddtrace layout
            from ddtrace.context import Context  # type: ignore[no-redef]
        from ddtrace import tracer
    except ImportError:
        return

    sc = trace.get_current_span().get_span_context()
    if not (sc and sc.is_valid):
        return
    tracer.context_provider.activate(Context(trace_id=sc.trace_id, span_id=sc.span_id))
