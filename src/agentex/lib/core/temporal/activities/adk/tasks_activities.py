from enum import Enum

from temporalio import activity

from agentex.lib.core.services.adk.tasks import TasksService
from agentex.types.task import Task
from agentex.lib.types.tracing import BaseModelWithTraceParams
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class TasksActivityName(str, Enum):
    GET_TASK = "get-task"
    DELETE_TASK = "delete-task"


class GetTaskParams(BaseModelWithTraceParams):
    task_id: str | None = None
    task_name: str | None = None


class DeleteTaskParams(BaseModelWithTraceParams):
    task_id: str | None = None
    task_name: str | None = None


class TasksActivities:
    def __init__(self, tasks_service: TasksService):
        self._tasks_service = tasks_service

    @activity.defn(name=TasksActivityName.GET_TASK)
    async def get_task(self, params: GetTaskParams) -> Task | None:
        return await self._tasks_service.get_task(
            task_id=params.task_id,
            task_name=params.task_name,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=TasksActivityName.DELETE_TASK)
    async def delete_task(self, params: DeleteTaskParams) -> Task:
        return await self._tasks_service.delete_task(
            task_id=params.task_id,
            task_name=params.task_name,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )
