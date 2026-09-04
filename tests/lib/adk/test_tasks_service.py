from __future__ import annotations

from unittest.mock import Mock, AsyncMock

import pytest

from agentex.types.task import Task
from agentex.lib.core.services.adk.tasks import TasksService


def _make_task(**overrides) -> Task:
    defaults = {
        "id": "task-123",
        "name": "test-task",
        "status": "RUNNING",
        "params": {},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    defaults.update(overrides)
    return Task(**defaults)


def _mock_span():
    mock_span = Mock()
    mock_span.output = None

    async def __aenter__(_self):
        return mock_span

    async def __aexit__(_self, *args):
        pass

    mock_span.__aenter__ = __aenter__
    mock_span.__aexit__ = __aexit__
    return mock_span


def _make_service() -> tuple[AsyncMock, TasksService]:
    mock_client = AsyncMock()
    mock_tracer = Mock()
    mock_trace = Mock()
    span = _mock_span()
    mock_trace.span.return_value = span
    mock_tracer.trace.return_value = mock_trace
    service = TasksService(agentex_client=mock_client, tracer=mock_tracer)
    return mock_client, service


class TestCancelTask:
    async def test_cancel_task(self):
        mock_client, service = _make_service()
        expected = _make_task(status="CANCELED")
        mock_client.tasks.cancel.return_value = expected

        result = await service.cancel_task(task_id="task-123", reason="done")

        assert result == expected
        mock_client.tasks.cancel.assert_called_once_with(task_id="task-123", reason="done")

    async def test_cancel_task_without_reason(self):
        mock_client, service = _make_service()
        expected = _make_task(status="CANCELED")
        mock_client.tasks.cancel.return_value = expected

        result = await service.cancel_task(task_id="task-123")

        assert result == expected
        mock_client.tasks.cancel.assert_called_once_with(task_id="task-123", reason=None)


class TestCompleteTask:
    async def test_complete_task(self):
        mock_client, service = _make_service()
        expected = _make_task(status="COMPLETED")
        mock_client.tasks.complete.return_value = expected

        result = await service.complete_task(task_id="task-123", reason="finished")

        assert result == expected
        mock_client.tasks.complete.assert_called_once_with(task_id="task-123", reason="finished")


class TestFailTask:
    async def test_fail_task(self):
        mock_client, service = _make_service()
        expected = _make_task(status="FAILED")
        mock_client.tasks.fail.return_value = expected

        result = await service.fail_task(task_id="task-123", reason="error")

        assert result == expected
        mock_client.tasks.fail.assert_called_once_with(task_id="task-123", reason="error")


class TestTerminateTask:
    async def test_terminate_task(self):
        mock_client, service = _make_service()
        expected = _make_task(status="TERMINATED")
        mock_client.tasks.terminate.return_value = expected

        result = await service.terminate_task(task_id="task-123", reason="killed")

        assert result == expected
        mock_client.tasks.terminate.assert_called_once_with(task_id="task-123", reason="killed")


class TestTimeoutTask:
    async def test_timeout_task(self):
        mock_client, service = _make_service()
        expected = _make_task(status="TIMED_OUT")
        mock_client.tasks.timeout.return_value = expected

        result = await service.timeout_task(task_id="task-123", reason="too slow")

        assert result == expected
        mock_client.tasks.timeout.assert_called_once_with(task_id="task-123", reason="too slow")


class TestUpdateTask:
    async def test_update_task_by_id(self):
        mock_client, service = _make_service()
        metadata = {"key": "value"}
        expected = _make_task(task_metadata=metadata)
        mock_client.tasks.update_by_id.return_value = expected

        result = await service.update_task(task_id="task-123", task_metadata=metadata)

        assert result == expected
        mock_client.tasks.update_by_id.assert_called_once_with(task_id="task-123", task_metadata=metadata)

    async def test_update_task_by_name(self):
        mock_client, service = _make_service()
        metadata = {"key": "value"}
        expected = _make_task(task_metadata=metadata)
        mock_client.tasks.update_by_name.return_value = expected

        result = await service.update_task(task_name="test-task", task_metadata=metadata)

        assert result == expected
        mock_client.tasks.update_by_name.assert_called_once_with(task_name="test-task", task_metadata=metadata)

    async def test_update_task_no_id_or_name_raises(self):
        _, service = _make_service()

        with pytest.raises(ValueError, match="Either task_id or task_name must be provided"):
            await service.update_task(task_metadata={"key": "value"})


class TestQueryWorkflow:
    async def test_query_workflow(self):
        mock_client, service = _make_service()
        expected = {"state": "processing", "progress": 50}
        mock_client.tasks.query_workflow.return_value = expected

        result = await service.query_workflow(task_id="task-123", query_name="get_progress")

        assert result == expected
        mock_client.tasks.query_workflow.assert_called_once_with(query_name="get_progress", task_id="task-123")
