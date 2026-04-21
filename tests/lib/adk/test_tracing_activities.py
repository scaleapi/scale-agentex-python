from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from temporalio.testing import ActivityEnvironment

from agentex.types.span import Span


def _make_span(**overrides) -> Span:
    defaults = {
        "id": "span-123",
        "name": "test-span",
        "start_time": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "trace_id": "trace-123",
    }
    defaults.update(overrides)
    return Span(**defaults)


def _make_tracing_activities():
    from agentex.lib.core.services.adk.tracing import TracingService
    from agentex.lib.core.temporal.activities.adk.tracing_activities import TracingActivities

    mock_service = AsyncMock(spec=TracingService)
    activities = TracingActivities(tracing_service=mock_service)
    env = ActivityEnvironment()
    return mock_service, activities, env


class TestStartSpanActivity:
    async def test_start_span_with_task_id(self):
        from agentex.lib.core.temporal.activities.adk.tracing_activities import StartSpanParams

        mock_service, activities, env = _make_tracing_activities()
        expected = _make_span(task_id="task-abc")
        mock_service.start_span.return_value = expected

        params = StartSpanParams(
            trace_id="trace-123",
            name="test-span",
            task_id="task-abc",
        )
        result = await env.run(activities.start_span, params)

        assert result == expected
        assert result.task_id == "task-abc"
        mock_service.start_span.assert_called_once_with(
            trace_id="trace-123",
            parent_id=None,
            name="test-span",
            input=None,
            data=None,
            task_id="task-abc",
        )

    async def test_start_span_without_task_id(self):
        from agentex.lib.core.temporal.activities.adk.tracing_activities import StartSpanParams

        mock_service, activities, env = _make_tracing_activities()
        expected = _make_span()
        mock_service.start_span.return_value = expected

        params = StartSpanParams(trace_id="trace-123", name="test-span")
        result = await env.run(activities.start_span, params)

        assert result == expected
        mock_service.start_span.assert_called_once_with(
            trace_id="trace-123",
            parent_id=None,
            name="test-span",
            input=None,
            data=None,
            task_id=None,
        )


class TestEndSpanActivity:
    async def test_end_span_preserves_task_id(self):
        from agentex.lib.core.temporal.activities.adk.tracing_activities import EndSpanParams

        mock_service, activities, env = _make_tracing_activities()
        span = _make_span(task_id="task-abc")
        expected = _make_span(
            task_id="task-abc",
            end_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        mock_service.end_span.return_value = expected

        params = EndSpanParams(trace_id="trace-123", span=span)
        result = await env.run(activities.end_span, params)

        assert result == expected
        assert result.task_id == "task-abc"
        mock_service.end_span.assert_called_once_with(trace_id="trace-123", span=span)
