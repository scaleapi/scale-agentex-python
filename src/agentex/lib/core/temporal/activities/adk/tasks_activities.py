from __future__ import annotations

from enum import Enum

from temporalio import activity

from agentex.types.task import Task
from agentex.lib.types.tracing import BaseModelWithTraceParams
from agentex.lib.utils.logging import make_logger
from agentex.lib.core.services.adk.tasks import TasksService
from agentex.types.task_retrieve_response import TaskRetrieveResponse
from agentex.types.task_retrieve_by_name_response import TaskRetrieveByNameResponse

logger = make_logger(__name__)


class TasksActivityName(str, Enum):
    GET_TASK = "get-task"
    DELETE_TASK = "delete-task"
    CANCEL_TASK = "cancel-task"
    COMPLETE_TASK = "complete-task"
    FAIL_TASK = "fail-task"
    TERMINATE_TASK = "terminate-task"
    TIMEOUT_TASK = "timeout-task"
    UPDATE_TASK = "update-task"
    QUERY_WORKFLOW = "query-workflow"


class GetTaskParams(BaseModelWithTraceParams):
    task_id: str | None = None
    task_name: str | None = None


class DeleteTaskParams(BaseModelWithTraceParams):
    task_id: str | None = None
    task_name: str | None = None


class TaskStatusTransitionParams(BaseModelWithTraceParams):
    task_id: str
    reason: str | None = None


class UpdateTaskParams(BaseModelWithTraceParams):
    task_id: str | None = None
    task_name: str | None = None
    task_metadata: dict[str, object] | None = None


class QueryWorkflowParams(BaseModelWithTraceParams):
    task_id: str
    query_name: str


class TasksActivities:
    def __init__(self, tasks_service: TasksService):
        self._tasks_service = tasks_service

    @activity.defn(name=TasksActivityName.GET_TASK)
    async def get_task(self, params: GetTaskParams) -> TaskRetrieveResponse | TaskRetrieveByNameResponse:
        return await self._tasks_service.get_task(
            task_id=params.task_id,
            task_name=params.task_name,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=TasksActivityName.DELETE_TASK)
    async def delete_task(self, params: DeleteTaskParams) -> Task:
        return await self._tasks_service.delete_task(  # type: ignore[return-value]
            task_id=params.task_id,
            task_name=params.task_name,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=TasksActivityName.CANCEL_TASK)
    async def cancel_task(self, params: TaskStatusTransitionParams) -> Task:
        return await self._tasks_service.cancel_task(
            task_id=params.task_id,
            reason=params.reason,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=TasksActivityName.COMPLETE_TASK)
    async def complete_task(self, params: TaskStatusTransitionParams) -> Task:
        return await self._tasks_service.complete_task(
            task_id=params.task_id,
            reason=params.reason,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=TasksActivityName.FAIL_TASK)
    async def fail_task(self, params: TaskStatusTransitionParams) -> Task:
        return await self._tasks_service.fail_task(
            task_id=params.task_id,
            reason=params.reason,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=TasksActivityName.TERMINATE_TASK)
    async def terminate_task(self, params: TaskStatusTransitionParams) -> Task:
        return await self._tasks_service.terminate_task(
            task_id=params.task_id,
            reason=params.reason,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=TasksActivityName.TIMEOUT_TASK)
    async def timeout_task(self, params: TaskStatusTransitionParams) -> Task:
        return await self._tasks_service.timeout_task(
            task_id=params.task_id,
            reason=params.reason,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=TasksActivityName.UPDATE_TASK)
    async def update_task(self, params: UpdateTaskParams) -> Task:
        return await self._tasks_service.update_task(
            task_id=params.task_id,
            task_name=params.task_name,
            task_metadata=params.task_metadata,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=TasksActivityName.QUERY_WORKFLOW)
    async def query_workflow(self, params: QueryWorkflowParams) -> dict[str, object]:
        return await self._tasks_service.query_workflow(
            task_id=params.task_id,
            query_name=params.query_name,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )
