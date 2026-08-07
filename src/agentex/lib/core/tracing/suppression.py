"""Suppress instrumentation while the tracing library exports its own telemetry.

Once a service instruments outbound HTTP, the library's own span export (shipping
business spans to egp / the Agentex control plane) becomes an instrumented HTTP
call. Those export spans nest into the very trace being exported and can dominate
it -- exporting a span gets traced, which triggers egp authz/identity/DB work
that is itself traced, and so on ("the camera pointed at its own monitor").

When ``SGP_OBS_SUPPRESS_EXPORT`` is enabled, wrapping the export in
``suppress_export_instrumentation()`` disables OTel instrumentation for the
duration: the export makes no spans and injects no ``traceparent``, so it can't
pollute or hijack the trace. The persistence still happens -- it just stops
being traced.

Opt-in, default OFF. Fail-open: a no-op if disabled or if OpenTelemetry's
instrumentation utils aren't importable, so observability can never break the
app path.
"""

from __future__ import annotations

import os
from typing import Iterator
from contextlib import contextmanager

_ENV = "SGP_OBS_SUPPRESS_EXPORT"


def suppress_export_enabled() -> bool:
    """True when ``SGP_OBS_SUPPRESS_EXPORT`` is set to a truthy value."""
    return os.environ.get(_ENV, "").strip().lower() in ("1", "true", "yes", "on")


@contextmanager
def suppress_export_instrumentation() -> Iterator[None]:
    """Disable OTel instrumentation for the wrapped telemetry-export block.

    Attaches OpenTelemetry's suppress-instrumentation context key so instrumentors
    (httpx, requests, ...) skip span creation AND context injection for any call
    made inside the block. The key rides the current contextvar, so it applies to
    an awaited export running in the same task. No-op when disabled or when OTel
    instrumentation isn't importable; never raises.
    """
    if not suppress_export_enabled():
        yield
        return
    try:
        from opentelemetry import context as _otel_context

        # Only present when opentelemetry-instrumentation is installed (agents),
        # not in the bare SDK env -- hence the guarded import + fail-open above.
        from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY  # type: ignore[import-not-found]
    except Exception:  # pragma: no cover - obs must never break the app path
        yield
        return
    token = _otel_context.attach(_otel_context.set_value(_SUPPRESS_INSTRUMENTATION_KEY, True))
    try:
        yield
    finally:
        try:
            _otel_context.detach(token)
        except Exception:  # pragma: no cover - best-effort
            pass
