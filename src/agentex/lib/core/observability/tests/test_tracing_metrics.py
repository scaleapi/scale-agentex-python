"""Tests for ``agentex.lib.core.observability.tracing_metrics``."""

from __future__ import annotations

import agentex.lib.core.observability.tracing_metrics as tracing_metrics
from agentex.lib.core.observability.tracing_metrics import (
    TracingMetrics,
    processor_label,
    get_tracing_metrics,
    classify_export_error,
)


class TestClassifyExportError:
    def test_scale_gp_authentication_error(self):
        class AuthenticationError(Exception):
            pass

        exc = AuthenticationError("Error code: 401 - {'message': 'Not authorized to access Account'}")
        assert classify_export_error(exc) == ("authentication", "401")

    def test_rate_limit_code(self):
        class APIError(Exception):
            pass

        exc = APIError("Error code: 429 - rate limited")
        assert classify_export_error(exc) == ("rate_limit", "429")

    def test_server_error_code(self):
        class APIError(Exception):
            pass

        exc = APIError("Error code: 503 - unavailable")
        assert classify_export_error(exc) == ("server_error", "5xx")

    def test_timeout_by_name(self):
        class APITimeoutError(Exception):
            pass

        assert classify_export_error(APITimeoutError("slow")) == ("timeout", "timeout")

    def test_unknown_error(self):
        class WeirdError(Exception):
            pass

        assert classify_export_error(WeirdError("boom")) == ("other_error", "unknown")


class TestProcessorLabel:
    def test_sgp_async_processor(self):
        class SGPAsyncTracingProcessor:
            pass

        assert processor_label(SGPAsyncTracingProcessor()) == "sgp"

    def test_other_processor(self):
        class AgentexAsyncTracingProcessor:
            pass

        assert processor_label(AgentexAsyncTracingProcessor()) == "other"


class TestGetTracingMetrics:
    def test_returns_tracing_metrics_instance(self, monkeypatch):
        monkeypatch.setattr(tracing_metrics, "_tracing_metrics", None)
        m = get_tracing_metrics()
        assert isinstance(m, TracingMetrics)

    def test_singleton_returns_same_instance(self, monkeypatch):
        monkeypatch.setattr(tracing_metrics, "_tracing_metrics", None)
        first = get_tracing_metrics()
        second = get_tracing_metrics()
        assert first is second

    def test_instruments_exist(self, monkeypatch):
        monkeypatch.setattr(tracing_metrics, "_tracing_metrics", None)
        m = get_tracing_metrics()
        for name in (
            "span_events_enqueued",
            "span_events_dropped",
            "queue_depth",
            "queue_lag_ms",
            "batch_items",
            "batch_size",
            "batch_drain_duration_ms",
            "export_batches",
            "export_spans",
            "export_batch_failures",
            "export_spans_failed",
            "shutdown_timeouts",
            "shutdown_remaining_items",
        ):
            assert hasattr(m, name), f"missing instrument: {name}"
