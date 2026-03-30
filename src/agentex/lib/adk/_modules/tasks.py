# ruff: noqa: I001
# Import order matters - AsyncTracer must come after client import to avoid circular imports
from __future__ import annotations
from datetime import timedelta

from temporalio.common import RetryPolicy

from agentex import AsyncAgentex  # noqa: F401
from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.services.adk.tasks import TasksService
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.temporal.activities.adk.tasks_activities import (
    DeleteTaskParams,
    GetTaskParams,
    QueryWorkflowParams,
    TasksActivityName,
    TaskStatusTransitionParams,
    UpdateTaskParams,
)
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.task import Task
from agentex.types.task_retrieve_response import TaskRetrieveResponse
from agentex.types.task_retrieve_by_name_response import TaskRetrieveByNameResponse
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
    ) -> TaskRetrieveResponse | TaskRetrieveByNameResponse:
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
            return await self._tasks_service.delete_task(  # type: ignore[return-value]
                task_id=task_id,
                task_name=task_name,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def cancel(
        self,
        *,
        task_id: str,
        reason: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> Task:
        """
        Mark a running task as canceled.
        Args:
            task_id: The ID of the task to cancel.
            reason: Optional reason for cancellation.
        Returns:
            The updated task entry.
        """
        params = TaskStatusTransitionParams(
            task_id=task_id,
            reason=reason,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=TasksActivityName.CANCEL_TASK,
                request=params,
                response_type=Task,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._tasks_service.cancel_task(
                task_id=task_id,
                reason=reason,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def complete(
        self,
        *,
        task_id: str,
        reason: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> Task:
        """
        Mark a running task as completed.
        Args:
            task_id: The ID of the task to complete.
            reason: Optional reason for completion.
        Returns:
            The updated task entry.
        """
        params = TaskStatusTransitionParams(
            task_id=task_id,
            reason=reason,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=TasksActivityName.COMPLETE_TASK,
                request=params,
                response_type=Task,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._tasks_service.complete_task(
                task_id=task_id,
                reason=reason,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def fail(
        self,
        *,
        task_id: str,
        reason: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> Task:
        """
        Mark a running task as failed.
        Args:
            task_id: The ID of the task to fail.
            reason: Optional reason for failure.
        Returns:
            The updated task entry.
        """
        params = TaskStatusTransitionParams(
            task_id=task_id,
            reason=reason,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=TasksActivityName.FAIL_TASK,
                request=params,
                response_type=Task,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._tasks_service.fail_task(
                task_id=task_id,
                reason=reason,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def terminate(
        self,
        *,
        task_id: str,
        reason: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> Task:
        """
        Mark a running task as terminated.
        Args:
            task_id: The ID of the task to terminate.
            reason: Optional reason for termination.
        Returns:
            The updated task entry.
        """
        params = TaskStatusTransitionParams(
            task_id=task_id,
            reason=reason,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=TasksActivityName.TERMINATE_TASK,
                request=params,
                response_type=Task,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._tasks_service.terminate_task(
                task_id=task_id,
                reason=reason,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def timeout(
        self,
        *,
        task_id: str,
        reason: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> Task:
        """
        Mark a running task as timed out.
        Args:
            task_id: The ID of the task to time out.
            reason: Optional reason for timeout.
        Returns:
            The updated task entry.
        """
        params = TaskStatusTransitionParams(
            task_id=task_id,
            reason=reason,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=TasksActivityName.TIMEOUT_TASK,
                request=params,
                response_type=Task,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._tasks_service.timeout_task(
                task_id=task_id,
                reason=reason,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def update(
        self,
        *,
        task_id: str | None = None,
        task_name: str | None = None,
        task_metadata: dict[str, object] | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> Task:
        """
        Update mutable fields for a task by ID or name.
        Args:
            task_id: The ID of the task to update.
            task_name: The name of the task to update.
            task_metadata: Metadata to update on the task.
        Returns:
            The updated task entry.
        """
        params = UpdateTaskParams(
            task_id=task_id,
            task_name=task_name,
            task_metadata=task_metadata,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=TasksActivityName.UPDATE_TASK,
                request=params,
                response_type=Task,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._tasks_service.update_task(
                task_id=task_id,
                task_name=task_name,
                task_metadata=task_metadata,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def query_workflow(
        self,
        *,
        task_id: str,
        query_name: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> dict[str, object]:
        """
        Query a Temporal workflow associated with a task for its current state.
        Args:
            task_id: The ID of the task whose workflow to query.
            query_name: The name of the query to execute.
        Returns:
            The query result.
        """
        params = QueryWorkflowParams(
            task_id=task_id,
            query_name=query_name,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=TasksActivityName.QUERY_WORKFLOW,
                request=params,
                response_type=dict,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._tasks_service.query_workflow(
                task_id=task_id,
                query_name=query_name,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )
