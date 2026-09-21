from __future__ import annotations

from unittest.mock import AsyncMock, patch

# Reference to the actual module object for patch.object
import agentex.lib.adk._modules.tasks as _tasks_mod
from agentex.types.task import Task
from agentex.lib.adk._modules.tasks import TasksModule
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


def _make_module() -> tuple[AsyncMock, TasksModule]:
    mock_service = AsyncMock(spec=TasksService)
    module = TasksModule(tasks_service=mock_service)
    return mock_service, module


class TestTasksModuleCancel:
    async def test_cancel(self):
        mock_service, module = _make_module()
        expected = _make_task(status="CANCELED")
        mock_service.cancel_task.return_value = expected

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=False):
            result = await module.cancel(task_id="task-123", reason="done")

        assert result == expected
        assert result.status == "CANCELED"
        mock_service.cancel_task.assert_called_once_with(
            task_id="task-123", reason="done", trace_id=None, parent_span_id=None
        )

    async def test_cancel_without_reason(self):
        mock_service, module = _make_module()
        expected = _make_task(status="CANCELED")
        mock_service.cancel_task.return_value = expected

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=False):
            result = await module.cancel(task_id="task-123")

        assert result == expected
        mock_service.cancel_task.assert_called_once_with(
            task_id="task-123", reason=None, trace_id=None, parent_span_id=None
        )


class TestTasksModuleComplete:
    async def test_complete(self):
        mock_service, module = _make_module()
        expected = _make_task(status="COMPLETED")
        mock_service.complete_task.return_value = expected

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=False):
            result = await module.complete(task_id="task-123", reason="finished")

        assert result == expected
        assert result.status == "COMPLETED"
        mock_service.complete_task.assert_called_once_with(
            task_id="task-123", reason="finished", trace_id=None, parent_span_id=None
        )


class TestTasksModuleFail:
    async def test_fail(self):
        mock_service, module = _make_module()
        expected = _make_task(status="FAILED")
        mock_service.fail_task.return_value = expected

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=False):
            result = await module.fail(task_id="task-123", reason="error occurred")

        assert result == expected
        assert result.status == "FAILED"
        mock_service.fail_task.assert_called_once_with(
            task_id="task-123", reason="error occurred", trace_id=None, parent_span_id=None
        )


class TestTasksModuleTerminate:
    async def test_terminate(self):
        mock_service, module = _make_module()
        expected = _make_task(status="TERMINATED")
        mock_service.terminate_task.return_value = expected

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=False):
            result = await module.terminate(task_id="task-123", reason="admin kill")

        assert result == expected
        assert result.status == "TERMINATED"
        mock_service.terminate_task.assert_called_once_with(
            task_id="task-123", reason="admin kill", trace_id=None, parent_span_id=None
        )


class TestTasksModuleTimeout:
    async def test_timeout(self):
        mock_service, module = _make_module()
        expected = _make_task(status="TIMED_OUT")
        mock_service.timeout_task.return_value = expected

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=False):
            result = await module.timeout(task_id="task-123", reason="exceeded limit")

        assert result == expected
        assert result.status == "TIMED_OUT"
        mock_service.timeout_task.assert_called_once_with(
            task_id="task-123", reason="exceeded limit", trace_id=None, parent_span_id=None
        )


class TestTasksModuleUpdate:
    async def test_update_by_id(self):
        mock_service, module = _make_module()
        metadata = {"key": "value"}
        expected = _make_task(task_metadata=metadata)
        mock_service.update_task.return_value = expected

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=False):
            result = await module.update(task_id="task-123", task_metadata=metadata)

        assert result == expected
        mock_service.update_task.assert_called_once_with(
            task_id="task-123", task_name=None, task_metadata=metadata, trace_id=None, parent_span_id=None
        )

    async def test_update_by_name(self):
        mock_service, module = _make_module()
        metadata = {"foo": "bar"}
        expected = _make_task(task_metadata=metadata)
        mock_service.update_task.return_value = expected

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=False):
            result = await module.update(task_name="test-task", task_metadata=metadata)

        assert result == expected
        mock_service.update_task.assert_called_once_with(
            task_id=None, task_name="test-task", task_metadata=metadata, trace_id=None, parent_span_id=None
        )

    async def test_update_with_tracing(self):
        mock_service, module = _make_module()
        expected = _make_task()
        mock_service.update_task.return_value = expected

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=False):
            result = await module.update(
                task_id="task-123", task_metadata={"a": "b"}, trace_id="trace-1", parent_span_id="span-1"
            )

        assert result == expected
        mock_service.update_task.assert_called_once_with(
            task_id="task-123",
            task_name=None,
            task_metadata={"a": "b"},
            trace_id="trace-1",
            parent_span_id="span-1",
        )


class TestTasksModuleQueryWorkflow:
    async def test_query_workflow(self):
        mock_service, module = _make_module()
        expected = {"state": "processing", "progress": 50}
        mock_service.query_workflow.return_value = expected

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=False):
            result = await module.query_workflow(task_id="task-123", query_name="get_progress")

        assert result == expected
        mock_service.query_workflow.assert_called_once_with(
            task_id="task-123", query_name="get_progress", trace_id=None, parent_span_id=None
        )

    async def test_query_workflow_with_tracing(self):
        mock_service, module = _make_module()
        expected = {"done": True}
        mock_service.query_workflow.return_value = expected

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=False):
            result = await module.query_workflow(
                task_id="task-123", query_name="is_done", trace_id="t", parent_span_id="s"
            )

        assert result == expected
        mock_service.query_workflow.assert_called_once_with(
            task_id="task-123", query_name="is_done", trace_id="t", parent_span_id="s"
        )


class TestTasksModuleTemporalPath:
    async def test_cancel_in_workflow(self):
        mock_service, module = _make_module()
        expected = _make_task(status="CANCELED")

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=True), \
                patch.object(_tasks_mod, "ActivityHelpers") as mock_helpers:
            mock_helpers.execute_activity = AsyncMock(return_value=expected)
            result = await module.cancel(task_id="task-123", reason="test")

        assert result == expected
        mock_helpers.execute_activity.assert_called_once()
        mock_service.cancel_task.assert_not_called()

    async def test_complete_in_workflow(self):
        mock_service, module = _make_module()
        expected = _make_task(status="COMPLETED")

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=True), \
                patch.object(_tasks_mod, "ActivityHelpers") as mock_helpers:
            mock_helpers.execute_activity = AsyncMock(return_value=expected)
            result = await module.complete(task_id="task-123")

        assert result == expected
        mock_helpers.execute_activity.assert_called_once()
        mock_service.complete_task.assert_not_called()

    async def test_update_in_workflow(self):
        mock_service, module = _make_module()
        expected = _make_task()

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=True), \
                patch.object(_tasks_mod, "ActivityHelpers") as mock_helpers:
            mock_helpers.execute_activity = AsyncMock(return_value=expected)
            result = await module.update(task_id="task-123", task_metadata={"k": "v"})

        assert result == expected
        mock_helpers.execute_activity.assert_called_once()
        mock_service.update_task.assert_not_called()

    async def test_query_workflow_in_workflow(self):
        mock_service, module = _make_module()
        expected = {"result": 42}

        with patch.object(_tasks_mod, "in_temporal_workflow", return_value=True), \
                patch.object(_tasks_mod, "ActivityHelpers") as mock_helpers:
            mock_helpers.execute_activity = AsyncMock(return_value=expected)
            result = await module.query_workflow(task_id="task-123", query_name="get_result")

        assert result == expected
        mock_helpers.execute_activity.assert_called_once()
        mock_service.query_workflow.assert_not_called()
