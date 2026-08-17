"""OpenTelemetry trace-context propagation across Temporal boundaries — DELEGATED.

The interceptor construction now lives in ``sgp_obs.traces.temporal``; this module
keeps the SDK's public surface (``temporal_trace_interceptor_enabled`` /
``temporal_tracing_interceptors``) and its
``AGENTEX_TEMPORAL_TRACE_INTERCEPTOR_ENABLED`` env toggle, delegating the actual
``TracingInterceptor`` to sgp_obs.

Temporal serializes ``start_workflow`` / ``execute_activity`` across (possibly
cross-process) boundaries and does not carry the active W3C ``traceparent`` by
default, so a span made inside a workflow/activity would otherwise become a new
detached root. temporalio's first-party interceptor injects + continues the
context so ``client -> workflow -> activity`` is one trace.
"""

from __future__ import annotations

import os
from typing import Any

from sgp_obs.traces import temporal as _sgp_temporal

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

_ENABLE_ENV = "AGENTEX_TEMPORAL_TRACE_INTERCEPTOR_ENABLED"
_FALSEY = {"0", "false", "no", "off"}


def temporal_trace_interceptor_enabled() -> bool:
    """Whether the Temporal OTel trace interceptor should be installed. Defaults
    to True; disabled only when ``AGENTEX_TEMPORAL_TRACE_INTERCEPTOR_ENABLED`` is a
    falsy value (``0`` / ``false`` / ``no`` / ``off``)."""
    return os.environ.get(_ENABLE_ENV, "true").strip().lower() not in _FALSEY


def temporal_tracing_interceptors() -> list[Any]:
    """Interceptors that propagate OpenTelemetry context across Temporal.

    Returns ``[TracingInterceptor()]`` (from sgp_obs, which implements both the
    client and worker interfaces) so callers splat it into a client's / worker's
    ``interceptors=``. Returns ``[]`` when disabled via env, or when temporalio's
    OpenTelemetry contrib isn't importable. Never raises — obs wiring must not
    break a worker.
    """
    if not temporal_trace_interceptor_enabled():
        logger.info("Temporal OTel trace interceptor disabled via %s", _ENABLE_ENV)
        return []
    return _sgp_temporal.interceptors()
