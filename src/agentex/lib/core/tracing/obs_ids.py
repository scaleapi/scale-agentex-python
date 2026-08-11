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

Source selection follows SGP_OBS_MODE:
  - unset / "dd_only": ddtrace context (current stack)
  - "lgtm":            OTel/LGTM only

("dual" was removed: co-resident ddtrace+OTel can't be bridged in-process --
you can't run ddtrace-run and the OTel operator's auto-instrumentation in the
same process, and DD_TRACE_OTEL_ENABLED yields a single tracer with nothing to
bridge. Two-backend export is a collector fan-out under "lgtm", not a mode here.
An unrecognized SGP_OBS_MODE -- including a stale "dual" -- degrades to dd_only.)

This never fabricates ids -- if no observability context is active, it returns
an empty dict and the span is simply not tagged.
"""

from __future__ import annotations

import os
import logging
from typing import Dict, Tuple, Optional

__all__ = ("get_obs_mode", "obs_correlation", "warn_on_backend_drift")

DD_ONLY = "dd_only"
LGTM = "lgtm"
_DEFAULT_MODE = DD_ONLY
_VALID_MODES = (DD_ONLY, LGTM)

_log = logging.getLogger(__name__)
# Deduped (expected, actual) drift directions already warned about, so a genuine
# mismatch logs once instead of once per span. Bounded by construction: at most
# the 2 direction pairs ("otel"/"ddtrace" either way).
_WARNED_DRIFT: set[Tuple[str, str]] = set()


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
        from ddtrace.trace import tracer
    except ImportError:
        return None
    ctx = tracer.current_trace_context()
    if ctx and ctx.trace_id:
        return format(ctx.trace_id, "032x"), format(ctx.span_id or 0, "016x")
    return None


def obs_correlation(expect_otel: bool = False) -> Dict[str, str]:
    """Return ``{"obs_trace_id": ..., "obs_span_id": ...}`` for the active
    observability context, or ``{}`` if none is active.

    These land in the business span's ``data`` -> egp ``operation_metadata``
    (an existing JSONB column, GIN-indexed) -> ClickHouse ``metadata_raw``, so
    the correlation edge needs no schema migration. Underscored keys (not
    dotted) keep them addressable via Postgres JSON paths
    (``operation_metadata->>'obs_trace_id'``).

    ``expect_otel``: on the Temporal path the active span is the temporalio OTel
    ``TracingInterceptor`` span regardless of ``SGP_OBS_MODE``, so callers there
    read OTel first (falling back to ddtrace) -- otherwise the default ``dd_only``
    mode would read ids for an unrelated ddtrace trace, not the activity span.

    Never fabricates ids -- this is a correlation tag, not the span's id.
    """
    try:
        if expect_otel:
            ids = _lgtm_ids() or _ddtrace_ids()
        else:
            ids = _lgtm_ids() if get_obs_mode() == LGTM else _ddtrace_ids()
    except Exception:  # obs must never fail an app call
        return {}

    if not ids:
        return {}
    return {"obs_trace_id": ids[0], "obs_span_id": ids[1]}


def warn_on_backend_drift(expect_otel: bool = False) -> None:
    """Log once when the EXPECTED obs backend has no active span but the OTHER one
    does.

    Expected backend = OTel when ``expect_otel`` (the Temporal path, where the
    interceptor span is OTel regardless of ``SGP_OBS_MODE``), otherwise the backend
    the mode implies. A mismatch means the mode does not match the tracer actually
    running at this call site -- e.g. ``dd_only`` configured but the live span is
    OTel -- which is a real config/instrumentation drift worth surfacing rather
    than silently correlating against whatever happens to be live.

    Not a hard failure: obs stays fail-open (the caller still reads and falls back,
    so no correlation is lost). The warning is deduped per direction, so a standing
    mismatch logs once, not once per span. Probes the expected backend first and
    returns early when it is live, so the healthy common path never touches the
    other backend. Never raises."""
    try:
        if expect_otel or get_obs_mode() == LGTM:
            expected, expected_probe, other_probe, actual = "otel", _lgtm_ids, _ddtrace_ids, "ddtrace"
        else:
            expected, expected_probe, other_probe, actual = "ddtrace", _ddtrace_ids, _lgtm_ids, "otel"
        if expected_probe() is not None:
            return  # expected backend is live -> healthy; skip the other probe
        if other_probe() is None:
            return  # nothing live at all -> uninstrumented path, not drift
        if (expected, actual) not in _WARNED_DRIFT:
            _WARNED_DRIFT.add((expected, actual))
            _log.warning(
                "obs backend drift: expected %s here (SGP_OBS_MODE=%s%s) but the "
                "active span is %s; correlating against %s. Check SGP_OBS_MODE and "
                "the running instrumentation.",
                expected,
                get_obs_mode(),
                ", temporal path" if expect_otel else "",
                actual,
                actual,
            )
    except Exception:  # obs must never fail an app call
        pass
