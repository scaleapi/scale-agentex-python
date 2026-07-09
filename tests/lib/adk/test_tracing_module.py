from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.exceptions import ActivityError

import agentex.lib.adk._modules.tracing as _tracing_mod
from agentex.types.span import Span
from agentex.lib.adk._modules.tracing import TurnSpan, TracingModule
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


def _make_activity_error() -> ActivityError:
    return ActivityError(
        "activity timed out",
        scheduled_event_id=1,
        started_event_id=2,
        identity="worker-1",
        activity_type="start-span",
        activity_id="activity-1",
        retry_state=None,
    )


def _make_metric_meter() -> MagicMock:
    mock_meter = MagicMock()
    mock_meter.create_counter.return_value = MagicMock()
    return mock_meter


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


class TestTracingModuleTemporalPath:
    async def test_start_span_in_workflow_returns_none_when_activity_fails(self):
        mock_service, module = _make_module()
        mock_meter = _make_metric_meter()

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=True), \
                patch.object(_tracing_mod, "ActivityHelpers") as mock_helpers, \
                patch.object(_tracing_mod.workflow, "logger") as mock_logger, \
                patch.object(_tracing_mod.workflow, "metric_meter", return_value=mock_meter):
            mock_helpers.execute_activity = AsyncMock(side_effect=_make_activity_error())
            result = await module.start_span(trace_id="trace-123", name="test-span")

        assert result is None
        mock_logger.warning.assert_called_once()
        mock_meter.create_counter.assert_called_once_with(
            _tracing_mod.TEMPORAL_SPAN_ACTIVITY_DROPPED_METRIC,
            description="Temporal tracing span activities dropped after fail-open",
            unit="1",
        )
        mock_meter.create_counter.return_value.add.assert_called_once_with(
            1, {"event_type": "start"}
        )
        mock_helpers.execute_activity.assert_called_once()
        mock_service.start_span.assert_not_called()

    async def test_end_span_in_workflow_returns_span_when_activity_fails(self):
        mock_service, module = _make_module()
        span = _make_span()
        mock_meter = _make_metric_meter()

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=True), \
                patch.object(_tracing_mod, "ActivityHelpers") as mock_helpers, \
                patch.object(_tracing_mod.workflow, "logger") as mock_logger, \
                patch.object(_tracing_mod.workflow, "metric_meter", return_value=mock_meter):
            mock_helpers.execute_activity = AsyncMock(side_effect=_make_activity_error())
            result = await module.end_span(trace_id="trace-123", span=span)

        assert result == span
        mock_logger.warning.assert_called_once()
        mock_meter.create_counter.assert_called_once_with(
            _tracing_mod.TEMPORAL_SPAN_ACTIVITY_DROPPED_METRIC,
            description="Temporal tracing span activities dropped after fail-open",
            unit="1",
        )
        mock_meter.create_counter.return_value.add.assert_called_once_with(
            1, {"event_type": "end"}
        )
        mock_helpers.execute_activity.assert_called_once()
        mock_service.end_span.assert_not_called()

    async def test_context_manager_skips_end_when_temporal_start_fails(self):
        mock_service, module = _make_module()

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=True), \
                patch.object(_tracing_mod, "ActivityHelpers") as mock_helpers, \
                patch.object(_tracing_mod.workflow, "logger"):
            mock_helpers.execute_activity = AsyncMock(side_effect=_make_activity_error())
            async with module.span(trace_id="trace-123", name="test-span") as span:
                assert span is None

        mock_helpers.execute_activity.assert_called_once()
        mock_service.start_span.assert_not_called()
        mock_service.end_span.assert_not_called()

    async def test_start_span_in_workflow_propagates_unexpected_errors(self):
        mock_service, module = _make_module()

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=True), \
                patch.object(_tracing_mod, "ActivityHelpers") as mock_helpers:
            mock_helpers.execute_activity = AsyncMock(side_effect=RuntimeError("bad response shape"))
            try:
                await module.start_span(trace_id="trace-123", name="test-span")
            except RuntimeError as exc:
                assert str(exc) == "bad response shape"
            else:
                raise AssertionError("Expected unexpected errors to propagate")

        mock_helpers.execute_activity.assert_called_once()
        mock_service.start_span.assert_not_called()

    async def test_start_span_in_workflow_propagates_cancellation(self):
        mock_service, module = _make_module()
        activity_error = _make_activity_error()
        mock_meter = _make_metric_meter()

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=True), \
                patch.object(_tracing_mod, "ActivityHelpers") as mock_helpers, \
                patch.object(_tracing_mod, "is_cancelled_exception", return_value=True), \
                patch.object(_tracing_mod.workflow, "logger") as mock_logger, \
                patch.object(_tracing_mod.workflow, "metric_meter", return_value=mock_meter):
            mock_helpers.execute_activity = AsyncMock(side_effect=activity_error)

            with pytest.raises(ActivityError):
                await module.start_span(trace_id="trace-123", name="test-span")

        mock_logger.warning.assert_not_called()
        mock_meter.create_counter.assert_not_called()
        mock_helpers.execute_activity.assert_called_once()
        mock_service.start_span.assert_not_called()

    async def test_end_span_in_workflow_propagates_cancellation(self):
        mock_service, module = _make_module()
        span = _make_span()
        activity_error = _make_activity_error()
        mock_meter = _make_metric_meter()

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=True), \
                patch.object(_tracing_mod, "ActivityHelpers") as mock_helpers, \
                patch.object(_tracing_mod, "is_cancelled_exception", return_value=True), \
                patch.object(_tracing_mod.workflow, "logger") as mock_logger, \
                patch.object(_tracing_mod.workflow, "metric_meter", return_value=mock_meter):
            mock_helpers.execute_activity = AsyncMock(side_effect=activity_error)

            with pytest.raises(ActivityError):
                await module.end_span(trace_id="trace-123", span=span)

        mock_logger.warning.assert_not_called()
        mock_meter.create_counter.assert_not_called()
        mock_helpers.execute_activity.assert_called_once()
        mock_service.end_span.assert_not_called()


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


class TestTurnSpan:
    async def test_turn_span_records_aggregate_usage_in_data(self):
        mock_service, module = _make_module()
        started = _make_span(task_id="task-abc")
        mock_service.start_span.return_value = started
        mock_service.end_span.return_value = started

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=False):
            async with module.turn_span(
                trace_id="trace-123",
                name="turn",
                task_id="task-abc",
            ) as turn:
                assert isinstance(turn, TurnSpan)
                turn.output = {"response": "hello"}
                turn.record_usage(
                    usage={"input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
                    cost_usd=0.0125,
                )

        ended_span = mock_service.end_span.call_args.kwargs["span"]
        assert ended_span.data["usage"] == {
            "input_tokens": 100,
            "output_tokens": 40,
            "total_tokens": 140,
        }
        assert ended_span.data["cost_usd"] == 0.0125
        # The aggregate lives in data, never in output — output stays payload-only
        assert ended_span.output == {"response": "hello"}

    async def test_turn_span_record_usage_with_individual_counts(self):
        mock_service, module = _make_module()
        started = _make_span()
        mock_service.start_span.return_value = started
        mock_service.end_span.return_value = started

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=False):
            async with module.turn_span(trace_id="trace-123", name="turn") as turn:
                turn.record_usage(input_tokens=10, output_tokens=5, cached_input_tokens=2)

        ended_span = mock_service.end_span.call_args.kwargs["span"]
        assert ended_span.data["usage"] == {
            "input_tokens": 10,
            "output_tokens": 5,
            "cached_input_tokens": 2,
        }

    async def test_turn_span_preserves_existing_data(self):
        mock_service, module = _make_module()
        started = _make_span(data={"custom": "value"})
        mock_service.start_span.return_value = started
        mock_service.end_span.return_value = started

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=False):
            async with module.turn_span(trace_id="trace-123", name="turn", data={"custom": "value"}) as turn:
                turn.record_usage(usage={"prompt_tokens": 3, "completion_tokens": 4})

        ended_span = mock_service.end_span.call_args.kwargs["span"]
        assert ended_span.data["custom"] == "value"
        assert ended_span.data["usage"] == {"prompt_tokens": 3, "completion_tokens": 4}

    async def test_turn_span_cost_only(self):
        mock_service, module = _make_module()
        started = _make_span()
        mock_service.start_span.return_value = started
        mock_service.end_span.return_value = started

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=False):
            async with module.turn_span(trace_id="trace-123", name="turn") as turn:
                turn.record_usage(cost_usd=0.5)

        ended_span = mock_service.end_span.call_args.kwargs["span"]
        assert ended_span.data == {"cost_usd": 0.5}
        assert "usage" not in ended_span.data

    async def test_turn_span_noop_when_no_trace_id(self):
        mock_service, module = _make_module()

        with patch.object(_tracing_mod, "in_temporal_workflow", return_value=False):
            async with module.turn_span(trace_id="", name="turn") as turn:
                assert turn.span is None
                # Must not raise when tracing is disabled
                turn.record_usage(usage={"input_tokens": 1}, cost_usd=0.1)
                turn.output = {"response": "x"}
                assert turn.output is None

        mock_service.start_span.assert_not_called()
        mock_service.end_span.assert_not_called()
