"""OpenTelemetry trace-context propagation across Temporal boundaries.

Temporal serializes ``start_workflow`` / ``execute_activity`` across (potentially
cross-process) boundaries, and does NOT carry the active W3C ``traceparent`` by
default. So any span created inside a workflow or activity becomes a **new
detached root** -- the trace shatters at every Temporal hop.

This bites agentex directly: ``adk.tracing.span`` runs span creation as a
Temporal activity when ``in_temporal_workflow()`` is true, so without propagation
those business spans detach from the turn's obs trace.

Wiring temporalio's first-party ``TracingInterceptor`` onto the Temporal client
and worker injects the active span context into Temporal headers on the caller
side and extracts + continues it on the workflow/activity side, using the global
OpenTelemetry propagator -- so ``client -> workflow -> activity`` is one trace.

Enabled by DEFAULT. Set ``AGENTEX_TEMPORAL_TRACE_INTERCEPTOR_ENABLED=false``
(also accepts ``0`` / ``no`` / ``off``) to turn it off. It also degrades to a
no-op -- and never raises -- if temporalio's OpenTelemetry contrib isn't
importable, so enabling it by default can't break a worker.
"""

from __future__ import annotations

import os
from typing import Any

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

_ENABLE_ENV = "AGENTEX_TEMPORAL_TRACE_INTERCEPTOR_ENABLED"
_FALSEY = {"0", "false", "no", "off"}


def temporal_trace_interceptor_enabled() -> bool:
    """Whether the Temporal OTel trace interceptor should be installed.

    Defaults to True; disabled only when ``AGENTEX_TEMPORAL_TRACE_INTERCEPTOR_ENABLED``
    is set to a falsy value (``0`` / ``false`` / ``no`` / ``off``)."""
    return os.environ.get(_ENABLE_ENV, "true").strip().lower() not in _FALSEY


def temporal_tracing_interceptors() -> list[Any]:
    """Interceptors that propagate OpenTelemetry trace context across Temporal.

    Returns ``[TracingInterceptor()]`` (enabled by default) so callers can splat
    it into a client's / worker's ``interceptors=`` list. Returns ``[]`` when
    disabled via env, or when temporalio's OpenTelemetry contrib is not
    importable. Never raises -- observability wiring must not break a worker.

    ``TracingInterceptor`` implements both the client and worker interceptor
    interfaces, so the same call is used on both sides:
      - on the **client**, it injects context on outbound ``start_workflow`` /
        ``execute_activity`` calls;
      - on the **worker**, it extracts context and roots the workflow / activity
        execution spans under it.
    """
    if not temporal_trace_interceptor_enabled():
        logger.info("Temporal OTel trace interceptor disabled via %s", _ENABLE_ENV)
        return []
    try:
        from temporalio.contrib.opentelemetry import TracingInterceptor

        # Construct inside the try so a constructor failure (not just a missing
        # contrib) also falls back to a no-op instead of aborting worker startup.
        return [TracingInterceptor()]
    except Exception as exc:  # contrib unavailable OR constructor failure -> no-op, never raise
        logger.warning(
            "Temporal OTel trace interceptor unavailable (%s); traces will not propagate across Temporal boundaries.",
            exc,
        )
        return []
