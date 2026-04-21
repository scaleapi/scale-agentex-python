from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import agentex.lib.adk._modules.tracing as _tracing_mod
from agentex.types.span import Span
from agentex.lib.adk._modules.tracing import TracingModule
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


def _make_module() -> tuple[AsyncMock, TracingModule]:
    mock_service = AsyncMock(spec=TracingService)
    module = TracingModule(tracing_service=mock_service)
    return mock_service, module


class TestStartSpan:
    async def test_start_span_with_task_id(self):
        mock_service, module = _make_module()
        expected = _make_span(task_id="task-abc")
        mock_service.start_span.return_value = expected

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=False):
            result = await module.start_span(
                trace_id="trace-123",
                name="test-span",
                task_id="task-abc",
            )

        assert result == expected
        assert result.task_id == "task-abc"
        mock_service.start_span.assert_called_once_with(
            trace_id="trace-123",
            name="test-span",
            input=None,
            parent_id=None,
            data=None,
            task_id="task-abc",
        )

    async def test_start_span_without_task_id(self):
        mock_service, module = _make_module()
        expected = _make_span()
        mock_service.start_span.return_value = expected

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=False):
            result = await module.start_span(trace_id="trace-123", name="test-span")

        assert result == expected
        mock_service.start_span.assert_called_once_with(
            trace_id="trace-123",
            name="test-span",
            input=None,
            parent_id=None,
            data=None,
            task_id=None,
        )


class TestEndSpan:
    async def test_end_span_preserves_task_id(self):
        mock_service, module = _make_module()
        span = _make_span(task_id="task-abc")
        expected = _make_span(
            task_id="task-abc",
            end_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        mock_service.end_span.return_value = expected

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=False):
            result = await module.end_span(trace_id="trace-123", span=span)

        assert result == expected
        assert result.task_id == "task-abc"
        mock_service.end_span.assert_called_once_with(trace_id="trace-123", span=span)


class TestSpanContextManager:
    async def test_span_context_manager_forwards_task_id(self):
        mock_service, module = _make_module()
        started = _make_span(task_id="task-abc")
        mock_service.start_span.return_value = started
        mock_service.end_span.return_value = started

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=False):
            async with module.span(
                trace_id="trace-123",
                name="test-span",
                task_id="task-abc",
            ) as span:
                assert span is not None
                assert span.task_id == "task-abc"

        assert mock_service.start_span.call_args.kwargs["task_id"] == "task-abc"
        mock_service.end_span.assert_called_once()

    async def test_span_context_manager_noop_when_no_trace_id(self):
        mock_service, module = _make_module()

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=False):
            async with module.span(trace_id="", name="test-span") as span:
                assert span is None

        mock_service.start_span.assert_not_called()
        mock_service.end_span.assert_not_called()
