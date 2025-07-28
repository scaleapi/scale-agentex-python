from datetime import timedelta

from temporalio.common import RetryPolicy

from agentex import AsyncAgentex
from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.services.adk.tasks import TasksService
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.temporal.activities.adk.tasks_activities import (
    DeleteTaskParams,
    GetTaskParams,
    TasksActivityName,
)
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.task import Task
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import in_temporal_workflow

logger = make_logger(__name__)

DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


class TasksModule:
    """
    Module for managing tasks in Agentex.
    Provides high-level async methods for retrieving, listing, and deleting tasks.
    """

    def __init__(
        self,
        tasks_service: TasksService | None = None,
    ):
        if tasks_service is None:
            agentex_client = create_async_agentex_client()
            tracer = AsyncTracer(agentex_client)
            self._tasks_service = TasksService(
                agentex_client=agentex_client, tracer=tracer
            )
        else:
            self._tasks_service = tasks_service

    async def get(
        self,
        *,
        task_id: str | None = None,
        task_name: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> Task:
        """
        Get a task by ID or name.
        Args:
            task_id: The ID of the task to retrieve.
            task_name: The name of the task to retrieve.
        Returns:
            The task entry.
        """
        params = GetTaskParams(
            task_id=task_id,
            task_name=task_name,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=TasksActivityName.GET_TASK,
                request=params,
                response_type=Task,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._tasks_service.get_task(
                task_id=task_id,
                task_name=task_name,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def delete(
        self,
        *,
        task_id: str | None = None,
        task_name: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> Task:
        """
        Delete a task by ID or name.
        Args:
            task_id: The ID of the task to delete.
            task_name: The name of the task to delete.
        Returns:
            The deleted task entry.
        """
        params = DeleteTaskParams(
            task_id=task_id,
            task_name=task_name,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=TasksActivityName.DELETE_TASK,
                request=params,
                response_type=Task,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._tasks_service.delete_task(
                task_id=task_id,
                task_name=task_name,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )
