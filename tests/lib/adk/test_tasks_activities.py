from unittest.mock import AsyncMock

from temporalio.testing import ActivityEnvironment

from agentex.types.task import Task


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


def _make_tasks_activities():
    from agentex.lib.core.services.adk.tasks import TasksService
    from agentex.lib.core.temporal.activities.adk.tasks_activities import TasksActivities

    mock_service = AsyncMock(spec=TasksService)
    activities = TasksActivities(tasks_service=mock_service)
    env = ActivityEnvironment()
    return mock_service, activities, env


class TestGetTask:
    async def test_get_task_by_id(self):
        from agentex.lib.core.temporal.activities.adk.tasks_activities import GetTaskParams

        mock_service, activities, env = _make_tasks_activities()
        expected = _make_task()
        mock_service.get_task.return_value = expected

        params = GetTaskParams(task_id="task-123", trace_id="t", parent_span_id="s")
        result = await env.run(activities.get_task, params)

        assert result == expected
        mock_service.get_task.assert_called_once_with(
            task_id="task-123", task_name=None, trace_id="t", parent_span_id="s"
        )

    async def test_get_task_by_name(self):
        from agentex.lib.core.temporal.activities.adk.tasks_activities import GetTaskParams

        mock_service, activities, env = _make_tasks_activities()
        expected = _make_task()
        mock_service.get_task.return_value = expected

        params = GetTaskParams(task_name="test-task", trace_id="t", parent_span_id="s")
        result = await env.run(activities.get_task, params)

        assert result == expected
        mock_service.get_task.assert_called_once_with(
            task_id=None, task_name="test-task", trace_id="t", parent_span_id="s"
        )


class TestDeleteTask:
    async def test_delete_task_by_id(self):
        from agentex.lib.core.temporal.activities.adk.tasks_activities import DeleteTaskParams

        mock_service, activities, env = _make_tasks_activities()
        expected = _make_task(status="DELETED")
        mock_service.delete_task.return_value = expected

        params = DeleteTaskParams(task_id="task-123", trace_id="t", parent_span_id="s")
        result = await env.run(activities.delete_task, params)

        assert result == expected
        mock_service.delete_task.assert_called_once_with(
            task_id="task-123", task_name=None, trace_id="t", parent_span_id="s"
        )


class TestCancelTask:
    async def test_cancel_task(self):
        from agentex.lib.core.temporal.activities.adk.tasks_activities import TaskStatusTransitionParams

        mock_service, activities, env = _make_tasks_activities()
        expected = _make_task(status="CANCELED", status_reason="user requested")
        mock_service.cancel_task.return_value = expected

        params = TaskStatusTransitionParams(
            task_id="task-123", reason="user requested", trace_id="t", parent_span_id="s"
        )
        result = await env.run(activities.cancel_task, params)

        assert result == expected
        assert result.status == "CANCELED"
        mock_service.cancel_task.assert_called_once_with(
            task_id="task-123", reason="user requested", trace_id="t", parent_span_id="s"
        )

    async def test_cancel_task_without_reason(self):
        from agentex.lib.core.temporal.activities.adk.tasks_activities import TaskStatusTransitionParams

        mock_service, activities, env = _make_tasks_activities()
        expected = _make_task(status="CANCELED")
        mock_service.cancel_task.return_value = expected

        params = TaskStatusTransitionParams(task_id="task-123")
        result = await env.run(activities.cancel_task, params)

        assert result == expected
        mock_service.cancel_task.assert_called_once_with(
            task_id="task-123", reason=None, trace_id=None, parent_span_id=None
        )


class TestCompleteTask:
    async def test_complete_task(self):
        from agentex.lib.core.temporal.activities.adk.tasks_activities import TaskStatusTransitionParams

        mock_service, activities, env = _make_tasks_activities()
        expected = _make_task(status="COMPLETED", status_reason="all done")
        mock_service.complete_task.return_value = expected

        params = TaskStatusTransitionParams(
            task_id="task-123", reason="all done", trace_id="t", parent_span_id="s"
        )
        result = await env.run(activities.complete_task, params)

        assert result == expected
        assert result.status == "COMPLETED"
        mock_service.complete_task.assert_called_once_with(
            task_id="task-123", reason="all done", trace_id="t", parent_span_id="s"
        )


class TestFailTask:
    async def test_fail_task(self):
        from agentex.lib.core.temporal.activities.adk.tasks_activities import TaskStatusTransitionParams

        mock_service, activities, env = _make_tasks_activities()
        expected = _make_task(status="FAILED", status_reason="something broke")
        mock_service.fail_task.return_value = expected

        params = TaskStatusTransitionParams(
            task_id="task-123", reason="something broke", trace_id="t", parent_span_id="s"
        )
        result = await env.run(activities.fail_task, params)

        assert result == expected
        assert result.status == "FAILED"
        mock_service.fail_task.assert_called_once_with(
            task_id="task-123", reason="something broke", trace_id="t", parent_span_id="s"
        )


class TestTerminateTask:
    async def test_terminate_task(self):
        from agentex.lib.core.temporal.activities.adk.tasks_activities import TaskStatusTransitionParams

        mock_service, activities, env = _make_tasks_activities()
        expected = _make_task(status="TERMINATED", status_reason="admin kill")
        mock_service.terminate_task.return_value = expected

        params = TaskStatusTransitionParams(
            task_id="task-123", reason="admin kill", trace_id="t", parent_span_id="s"
        )
        result = await env.run(activities.terminate_task, params)

        assert result == expected
        assert result.status == "TERMINATED"
        mock_service.terminate_task.assert_called_once_with(
            task_id="task-123", reason="admin kill", trace_id="t", parent_span_id="s"
        )


class TestTimeoutTask:
    async def test_timeout_task(self):
        from agentex.lib.core.temporal.activities.adk.tasks_activities import TaskStatusTransitionParams

        mock_service, activities, env = _make_tasks_activities()
        expected = _make_task(status="TIMED_OUT", status_reason="exceeded 30s")
        mock_service.timeout_task.return_value = expected

        params = TaskStatusTransitionParams(
            task_id="task-123", reason="exceeded 30s", trace_id="t", parent_span_id="s"
        )
        result = await env.run(activities.timeout_task, params)

        assert result == expected
        assert result.status == "TIMED_OUT"
        mock_service.timeout_task.assert_called_once_with(
            task_id="task-123", reason="exceeded 30s", trace_id="t", parent_span_id="s"
        )


class TestUpdateTask:
    async def test_update_task_by_id(self):
        from agentex.lib.core.temporal.activities.adk.tasks_activities import UpdateTaskParams

        mock_service, activities, env = _make_tasks_activities()
        metadata = {"key": "value"}
        expected = _make_task(task_metadata=metadata)
        mock_service.update_task.return_value = expected

        params = UpdateTaskParams(
            task_id="task-123", task_metadata=metadata, trace_id="t", parent_span_id="s"
        )
        result = await env.run(activities.update_task, params)

        assert result == expected
        mock_service.update_task.assert_called_once_with(
            task_id="task-123", task_name=None, task_metadata=metadata, trace_id="t", parent_span_id="s"
        )

    async def test_update_task_by_name(self):
        from agentex.lib.core.temporal.activities.adk.tasks_activities import UpdateTaskParams

        mock_service, activities, env = _make_tasks_activities()
        metadata = {"foo": "bar"}
        expected = _make_task(task_metadata=metadata)
        mock_service.update_task.return_value = expected

        params = UpdateTaskParams(
            task_name="test-task", task_metadata=metadata, trace_id="t", parent_span_id="s"
        )
        result = await env.run(activities.update_task, params)

        assert result == expected
        mock_service.update_task.assert_called_once_with(
            task_id=None, task_name="test-task", task_metadata=metadata, trace_id="t", parent_span_id="s"
        )


class TestQueryWorkflow:
    async def test_query_workflow(self):
        from agentex.lib.core.temporal.activities.adk.tasks_activities import QueryWorkflowParams

        mock_service, activities, env = _make_tasks_activities()
        expected = {"state": "processing", "progress": 50}
        mock_service.query_workflow.return_value = expected

        params = QueryWorkflowParams(
            task_id="task-123", query_name="get_progress", trace_id="t", parent_span_id="s"
        )
        result = await env.run(activities.query_workflow, params)

        assert result == expected
        mock_service.query_workflow.assert_called_once_with(
            task_id="task-123", query_name="get_progress", trace_id="t", parent_span_id="s"
        )
