"""Unit tests for ACP inbound W3C trace-context extraction.

Regression guard for the async end-to-end tracing fix: FastACP must *continue*
an incoming traceparent (make it the active OpenTelemetry context) so the
downstream Temporal start/signal — and the work dispatched via
asyncio.create_task — run under the ingress trace instead of detaching into a
fresh trace. See RequestIDMiddleware / _attach_incoming_otel_context.
"""

from __future__ import annotations

from opentelemetry.propagate import inject

from agentex.lib.sdk.fastacp.base.base_acp_server import (
    _detach_otel_context,
    _attach_incoming_otel_context,
)


def _active_traceparent() -> str | None:
    carrier: dict[str, str] = {}
    inject(carrier)
    return carrier.get("traceparent")


def test_attach_makes_inbound_traceparent_the_active_context() -> None:
    trace_id = "0af7651916cd43dd8448eb211c80319c"
    headers = [
        (b"traceparent", f"00-{trace_id}-b7ad6b7169203331-01".encode()),
        (b"content-type", b"application/json"),
    ]
    token = _attach_incoming_otel_context(headers)
    try:
        active = _active_traceparent()
        assert active is not None, "no active traceparent after attach"
        # The active context must carry the ingress trace id, so the Temporal
        # interceptor propagates it downstream instead of starting a fresh trace.
        assert trace_id in active, f"expected ingress trace {trace_id}, got {active}"
    finally:
        _detach_otel_context(token)


def test_no_inbound_traceparent_is_fail_open() -> None:
    # No traceparent header: must not raise, and detach must be safe.
    token = _attach_incoming_otel_context([(b"content-type", b"application/json")])
    _detach_otel_context(token)


def test_detach_none_is_safe() -> None:
    _detach_otel_context(None)
