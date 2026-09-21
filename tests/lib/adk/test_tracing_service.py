from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from agentex.types.span import Span
from agentex.lib.core.services.adk.tracing import TracingService


def _make_span(**overrides) -> Span:
    defaults = {
        "id": "span-123",
        "name": "test-span",
        "start_time": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "trace_id": "trace-123",
    }
    defaults.update(overrides)
    return Span(**defaults)


def _make_service() -> tuple[MagicMock, MagicMock, TracingService]:
    """Build a TracingService backed by an AsyncTracer whose
    trace.start_span / trace.end_span are mocked."""
    mock_trace = MagicMock()
    mock_trace.start_span = AsyncMock()
    mock_trace.end_span = AsyncMock()

    mock_tracer = MagicMock()
    mock_tracer.trace.return_value = mock_trace

    service = TracingService(tracer=mock_tracer)
    return mock_tracer, mock_trace, service


class TestStartSpanService:
    async def test_start_span_passes_task_id(self):
        mock_tracer, mock_trace, service = _make_service()
        expected = _make_span(task_id="task-abc")
        mock_trace.start_span.return_value = expected

        result = await service.start_span(
            trace_id="trace-123",
            name="test-span",
            task_id="task-abc",
        )

        assert result == expected
        mock_tracer.trace.assert_called_once_with("trace-123")
        mock_trace.start_span.assert_awaited_once_with(
            name="test-span",
            parent_id=None,
            input={},
            data=None,
            task_id="task-abc",
        )

    async def test_start_span_without_task_id(self):
        _mock_tracer, mock_trace, service = _make_service()
        expected = _make_span()
        mock_trace.start_span.return_value = expected

        result = await service.start_span(trace_id="trace-123", name="test-span")

        assert result == expected
        mock_trace.start_span.assert_awaited_once_with(
            name="test-span",
            parent_id=None,
            input={},
            data=None,
            task_id=None,
        )


class TestEndSpanService:
    async def test_end_span_forwards_span(self):
        mock_tracer, mock_trace, service = _make_service()
        span = _make_span(task_id="task-abc")
        mock_trace.end_span.return_value = span

        result = await service.end_span(trace_id="trace-123", span=span)

        assert result is span
        mock_tracer.trace.assert_called_once_with("trace-123")
        mock_trace.end_span.assert_awaited_once_with(span)
