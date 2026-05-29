"""Best-effort recording helpers for span queue / export OTel metrics.

This module intentionally does **not** import OpenTelemetry — hot paths can
import it without pulling in the OTel SDK.  Instruments are created lazily on
first record when ``is_metrics_enabled()`` is true.
"""

from __future__ import annotations

import os
import time
from typing import Protocol, Sequence


class _HasEnqueuedAt(Protocol):
    enqueued_at: float | None


_metrics_enabled: bool | None = None
_tracing = None  # lazy-loaded tracing_metrics module (loads OTel on first use)


def is_metrics_enabled() -> bool:
    """Return whether SDK span-queue metrics recording is enabled."""
    global _metrics_enabled
    if _metrics_enabled is None:
        raw = os.environ.get("AGENTEX_TRACING_METRICS", "1").strip().lower()
        _metrics_enabled = raw not in ("0", "false", "no", "off")
    return _metrics_enabled


def _tracing_module():
    """Return lazy-loaded ``tracing_metrics`` module (loads OTel on first use)."""
    global _tracing
    if _tracing is None:
        from agentex.lib.core.observability import tracing_metrics

        _tracing = tracing_metrics
    return _tracing


def monotonic_if_enabled() -> float | None:
    """Return ``time.monotonic()`` when metrics are enabled, else ``None``."""
    if not is_metrics_enabled():
        return None
    return time.monotonic()


def record_span_enqueued(event_type: str) -> None:
    if not is_metrics_enabled():
        return
    try:
        _tracing_module().get_tracing_metrics().span_events_enqueued.add(
            1, {"event_type": event_type}
        )
    except Exception:
        pass


def record_span_dropped(reason: str) -> None:
    if not is_metrics_enabled():
        return
    try:
        _tracing_module().get_tracing_metrics().span_events_dropped.add(1, {"reason": reason})
    except Exception:
        pass


def record_batch_coalesced(
    *,
    queue_depth: int,
    batch_items: Sequence[_HasEnqueuedAt],
) -> None:
    if not is_metrics_enabled():
        return
    try:
        metrics = _tracing_module().get_tracing_metrics()
        metrics.queue_depth.record(max(queue_depth, 0))
        metrics.batch_items.record(len(batch_items))

        now = time.monotonic()
        lag_ms = 0.0
        for item in batch_items:
            if item.enqueued_at is None:
                continue
            lag_ms = max(lag_ms, (now - item.enqueued_at) * 1000.0)
        if lag_ms > 0:
            metrics.queue_lag.record(lag_ms)
    except Exception:
        pass


def record_batch_phase(*, phase: str, size: int, duration_ms: float) -> None:
    if not is_metrics_enabled():
        return
    try:
        attrs = {"phase": phase}
        metrics = _tracing_module().get_tracing_metrics()
        metrics.batch_size.record(size, attrs)
        metrics.batch_drain_duration.record(duration_ms, attrs)
    except Exception:
        pass


def record_export_success(*, event_type: str, span_count: int, processor: str) -> None:
    if not is_metrics_enabled():
        return
    try:
        attrs = {"processor": processor, "event_type": event_type}
        metrics = _tracing_module().get_tracing_metrics()
        metrics.export_batches.add(1, attrs)
        metrics.export_spans.add(span_count, attrs)
    except Exception:
        pass


def record_export_failure(
    *,
    processor: object,
    event_type: str,
    span_count: int,
    exc: BaseException,
) -> None:
    if not is_metrics_enabled():
        return
    try:
        tm = _tracing_module()
        error_class, http_code = tm.classify_export_error(exc)
        proc = tm.processor_label(processor)
        attrs = {
            "processor": proc,
            "event_type": event_type,
            "http_code": http_code,
            "error_class": error_class,
        }
        metrics = tm.get_tracing_metrics()
        metrics.export_batch_failures.add(1, attrs)
        metrics.export_span_failures.add(span_count, attrs)
    except Exception:
        pass


def record_shutdown_timeout(*, remaining_items: int) -> None:
    if not is_metrics_enabled():
        return
    try:
        metrics = _tracing_module().get_tracing_metrics()
        metrics.shutdown_timeouts.add(1)
        metrics.shutdown_remaining_items.record(max(remaining_items, 0))
    except Exception:
        pass
