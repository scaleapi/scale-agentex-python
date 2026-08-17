"""Correlate adk business spans with the active observability trace.

DELEGATES to ``sgp_obs`` (the shared SGP observability library). The id-reading
that used to live here (``_lgtm_ids`` / ``_ddtrace_ids``) now lives in
``sgp_obs.traces.backends``; this module keeps the SDK's public surface
(``get_obs_mode`` / ``obs_correlation`` + the ``DD_ONLY`` / ``LGTM`` constants) so
callers are unchanged.

Each business span is *tagged* with the active observability trace_id/span_id
(the OpenTelemetry "span link" pattern) so you can pivot a persisted business
span to its per-turn Tempo/Datadog trace, while the business trace still groups
the whole run by task id. Never fabricates ids — no active context returns ``{}``.

Source follows ``SGP_OBS_MODE``: unset/``dd_only`` -> ddtrace; ``lgtm`` -> OTel.
Note the SDK spells the OTel mode ``"lgtm"`` while ``sgp_obs.ObsMode`` spells it
``"otel"`` — :func:`obs_mode` maps between them.
"""

from __future__ import annotations

import os
from typing import Dict

from sgp_obs.traces import ObsMode
from sgp_obs.traces.backends.otel import OTelBackend
from sgp_obs.traces.backends.ddtrace import DDTraceBackend

__all__ = ("get_obs_mode", "obs_correlation", "DD_ONLY", "LGTM")

DD_ONLY = "dd_only"
LGTM = "lgtm"
_DEFAULT_MODE = DD_ONLY
_VALID_MODES = (DD_ONLY, LGTM)

# Stateless singletons — the backends hold no per-call state.
_OTEL = OTelBackend()
_DDTRACE = DDTraceBackend()


def get_obs_mode() -> str:
    """Unset/empty/unrecognized -> ``dd_only``. Returns the SDK's string form
    (``"lgtm"`` / ``"dd_only"``)."""
    raw = os.getenv("SGP_OBS_MODE")
    if not raw:
        return _DEFAULT_MODE
    mode = raw.strip().lower()
    return mode if mode in _VALID_MODES else _DEFAULT_MODE


def obs_mode() -> ObsMode:
    """The SDK's ``SGP_OBS_MODE`` mapped to ``sgp_obs.ObsMode`` (``lgtm`` -> OTEL,
    else DD_ONLY). Used to drive the sgp_obs Correlator/backends."""
    return ObsMode.OTEL if get_obs_mode() == LGTM else ObsMode.DD_ONLY


def obs_correlation(prefer_otel: bool = False) -> Dict[str, str]:
    """Return ``{"obs_trace_id": ..., "obs_span_id": ...}`` for the active obs
    context, or ``{}`` if none. Delegates id-reading to the sgp_obs backends'
    ``current_ids()``.

    ``prefer_otel``: read OTel first (on the Temporal path the active span is the
    temporalio OTel interceptor span regardless of ``SGP_OBS_MODE``). Never
    fabricates ids — this is a correlation tag, not the span's id.
    """
    try:
        if prefer_otel:
            corr = _OTEL.current_ids() or _DDTRACE.current_ids()
        else:
            corr = (_OTEL if get_obs_mode() == LGTM else _DDTRACE).current_ids()
    except Exception:  # obs must never fail an app call
        return {}
    return corr.as_metadata() if corr is not None else {}
