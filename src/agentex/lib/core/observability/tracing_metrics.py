"""OTel metrics for async span queue and SGP export telemetry.

Single source of truth for span-queue / export instrumentation.  Import
``get_tracing_metrics()`` or the ``record_*`` helpers in
``tracing_metrics_recording`` from hot paths — never configure a
``MeterProvider`` here.

The meter is no-op when the application has not configured a
``MeterProvider``.  Set ``AGENTEX_TRACING_METRICS=0`` to skip recording
entirely (see ``tracing_metrics_recording.is_metrics_enabled``).

Cardinality is bounded:
- ``event_type``: ``start`` | ``end``
- ``processor``: ``sgp`` | ``other``
- ``http_code``: small fixed set from ``classify_export_error`` (failure counters only)
- ``error_class``: small fixed set from ``classify_export_error`` (failure counters only)
- ``reason``: ``shutdown`` (drops only)
- ``phase``: ``start`` | ``end`` (batch drain histograms)

Resource attributes (``service.name``, ``k8s.*``, etc.) come from the
host application's OTel resource configuration.
"""

from __future__ import annotations

import re
from typing import Optional

from opentelemetry import metrics

_HTTP_CODE_RE = re.compile(r"Error code:\s*(\d+)")


class TracingMetrics:
    """Lazily-created OTel instruments for span queue + export telemetry."""

    def __init__(self) -> None:
        meter = metrics.get_meter("agentex.tracing")
        self.span_events_enqueued = meter.create_counter(
            name="agentex.tracing.span_events.enqueued",
            unit="1",
            description="Span queue START/END events accepted by enqueue()",
        )
        self.span_events_dropped = meter.create_counter(
            name="agentex.tracing.span_events.dropped",
            unit="1",
            description="Span queue events dropped (e.g. shutdown)",
        )
        self.queue_depth = meter.create_histogram(
            name="agentex.tracing.queue.depth",
            unit="1",
            description="asyncio queue depth at the start of a drain batch",
        )
        self.queue_lag = meter.create_histogram(
            name="agentex.tracing.queue.lag",
            unit="ms",
            description="Max time from enqueue to drain-batch start for items in the batch",
        )
        self.batch_items = meter.create_histogram(
            name="agentex.tracing.batch.items",
            unit="1",
            description="Total span events coalesced in one linger/drain batch",
        )
        self.batch_size = meter.create_histogram(
            name="agentex.tracing.batch.size",
            unit="1",
            description="Span events in one START or END dispatch phase",
        )
        self.batch_drain_duration = meter.create_histogram(
            name="agentex.tracing.batch.drain_duration",
            unit="ms",
            description="Wall time for one START or END _process_items dispatch",
        )
        self.export_batches = meter.create_counter(
            name="agentex.tracing.export.batches",
            unit="1",
            description="Successful HTTP export batches by processor and event type",
        )
        self.export_spans = meter.create_counter(
            name="agentex.tracing.export.spans",
            unit="1",
            description="Spans in successful HTTP export batches by processor and event type",
        )
        self.export_batch_failures = meter.create_counter(
            name="agentex.tracing.export.batch_failures",
            unit="1",
            description="Failed HTTP export batches by processor and HTTP status",
        )
        self.export_span_failures = meter.create_counter(
            name="agentex.tracing.export.span_failures",
            unit="1",
            description="Spans in failed HTTP export batches by processor and HTTP status",
        )
        self.shutdown_timeouts = meter.create_counter(
            name="agentex.tracing.shutdown.timeouts",
            unit="1",
            description="Span queue shutdown calls that hit the join timeout",
        )
        self.shutdown_remaining_items = meter.create_histogram(
            name="agentex.tracing.shutdown.remaining_items",
            unit="1",
            description="Queue depth when span queue shutdown times out",
        )


_tracing_metrics: Optional[TracingMetrics] = None


def get_tracing_metrics() -> TracingMetrics:
    """Return the tracing metrics singleton, creating it on first use."""
    global _tracing_metrics
    if _tracing_metrics is None:
        _tracing_metrics = TracingMetrics()
    return _tracing_metrics


def processor_label(processor: object) -> str:
    """Map a tracing processor instance to a low-cardinality label."""
    if type(processor).__name__ == "SGPAsyncTracingProcessor":
        return "sgp"
    return "other"


def classify_export_error(exc: BaseException) -> tuple[str, str]:
    """Categorize an export failure into (error_class, http_code_label).

    ``http_code_label`` is a small fixed set suitable for Prometheus labels.
    """
    name = type(exc).__name__
    message = str(exc)

    if "Timeout" in name:
        return "timeout", "timeout"
    if "Connection" in name or "Connect" in name:
        return "network_error", "network"

    match = _HTTP_CODE_RE.search(message)
    if match:
        code = int(match.group(1))
        if code == 401:
            return "authentication", "401"
        if code == 403:
            return "authentication", "403"
        if code == 429:
            return "rate_limit", "429"
        if 400 <= code < 500:
            return "client_error", "4xx"
        if 500 <= code < 600:
            return "server_error", "5xx"
        return "other_error", "other"

    if any(s in name for s in ("Authentication", "Permission")):
        return "authentication", "unknown"
    if "RateLimit" in name:
        return "rate_limit", "429"
    if any(s in name for s in ("ServerError", "InternalServer", "ServiceUnavailable", "BadGateway")):
        return "server_error", "5xx"
    if any(
        s in name
        for s in ("BadRequest", "NotFound", "Conflict", "UnprocessableEntity")
    ):
        return "client_error", "4xx"

    return "other_error", "unknown"
