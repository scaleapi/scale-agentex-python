"""Tests for ``agentex.lib.core.observability.tracing_metrics_recording``."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import agentex.lib.core.observability.tracing_metrics_recording as recording


class _Item:
    def __init__(self, enqueued_at: float | None) -> None:
        self.enqueued_at = enqueued_at


class TestIsMetricsEnabled:
    def setup_method(self) -> None:
        recording._metrics_enabled = None
        recording._tracing = None

    def test_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv("AGENTEX_TRACING_METRICS", raising=False)
        assert recording.is_metrics_enabled() is True

    def test_disabled_by_zero(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_METRICS", "0")
        recording._metrics_enabled = None
        assert recording.is_metrics_enabled() is False


class TestRecordingHelpers:
    def setup_method(self) -> None:
        recording._metrics_enabled = None
        recording._tracing = None

    def test_record_span_enqueued_when_disabled_does_not_load_metrics(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_METRICS", "0")
        recording._metrics_enabled = None
        with patch(
            "agentex.lib.core.observability.tracing_metrics.get_tracing_metrics"
        ) as mock_get:
            recording.record_span_enqueued("start")
            mock_get.assert_not_called()

    def test_record_span_enqueued_when_enabled(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_METRICS", "1")
        recording._metrics_enabled = None
        mock_metrics = MagicMock()
        with patch(
            "agentex.lib.core.observability.tracing_metrics.get_tracing_metrics",
            return_value=mock_metrics,
        ):
            recording.record_span_enqueued("end")
        mock_metrics.span_events_enqueued.add.assert_called_once_with(1, {"event_type": "end"})

    def test_monotonic_if_enabled_respects_kill_switch(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_METRICS", "0")
        recording._metrics_enabled = None
        assert recording.monotonic_if_enabled() is None

    def test_record_batch_coalesced_records_lag(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_METRICS", "1")
        recording._metrics_enabled = None
        mock_metrics = MagicMock()
        with patch(
            "agentex.lib.core.observability.tracing_metrics.get_tracing_metrics",
            return_value=mock_metrics,
        ), patch("agentex.lib.core.observability.tracing_metrics_recording.time.monotonic", return_value=10.0):
            recording.record_batch_coalesced(
                queue_depth=3,
                batch_items=[_Item(9.5), _Item(9.0)],
            )
        mock_metrics.queue_depth.record.assert_called_once_with(3)
        mock_metrics.batch_items.record.assert_called_once_with(2)
        mock_metrics.queue_lag.record.assert_called_once_with(1000.0)

    def test_record_export_failure(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_METRICS", "1")
        recording._metrics_enabled = None
        mock_metrics = MagicMock()

        class AuthenticationError(Exception):
            pass

        exc = AuthenticationError("Error code: 401 - denied")
        processor = type("SGPAsyncTracingProcessor", (), {})()

        with patch(
            "agentex.lib.core.observability.tracing_metrics.get_tracing_metrics",
            return_value=mock_metrics,
        ):
            recording.record_export_failure(
                processor=processor,
                event_type="start",
                span_count=5,
                exc=exc,
            )

        mock_metrics.export_batch_failures.add.assert_called_once()
        mock_metrics.export_span_failures.add.assert_called_once_with(
            5,
            {
                "processor": "sgp",
                "event_type": "start",
                "http_code": "401",
                "error_class": "authentication",
            },
        )

    def test_record_export_success(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_METRICS", "1")
        recording._metrics_enabled = None
        mock_metrics = MagicMock()
        with patch(
            "agentex.lib.core.observability.tracing_metrics.get_tracing_metrics",
            return_value=mock_metrics,
        ):
            recording.record_export_success(event_type="end", span_count=12, processor="sgp")

        mock_metrics.export_batches.add.assert_called_once_with(
            1,
            {"processor": "sgp", "event_type": "end"},
        )
        mock_metrics.export_spans.add.assert_called_once_with(
            12,
            {"processor": "sgp", "event_type": "end"},
        )

    def test_record_export_success_accepts_processor_label(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_METRICS", "1")
        recording._metrics_enabled = None
        mock_metrics = MagicMock()
        with patch(
            "agentex.lib.core.observability.tracing_metrics.get_tracing_metrics",
            return_value=mock_metrics,
        ):
            recording.record_export_success(
                event_type="start", span_count=3, processor="other"
            )

        mock_metrics.export_batches.add.assert_called_once_with(
            1,
            {"processor": "other", "event_type": "start"},
        )
