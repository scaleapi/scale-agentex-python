from agentex import AsyncAgentex
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.task import Task
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import heartbeat_if_in_workflow

logger = make_logger(__name__)


class TasksService:
    def __init__(
        self,
        agentex_client: AsyncAgentex,
        tracer: AsyncTracer,
    ):
        self._agentex_client = agentex_client
        self._tracer = tracer

    async def get_task(
        self,
        task_id: str | None = None,
        task_name: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Task:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="get_task",
            input={"task_id": task_id, "task_name": task_name},
        ) as span:
            heartbeat_if_in_workflow("get task")
            if not task_id and not task_name:
                raise ValueError("Either task_id or task_name must be provided.")
            if task_id:
                task_model = await self._agentex_client.tasks.retrieve(task_id=task_id)
            elif task_name:
                task_model = await self._agentex_client.tasks.retrieve_by_name(task_name=task_name)
            else:
                raise ValueError("Either task_id or task_name must be provided.")
            if span:
                span.output = task_model.model_dump()
            return task_model

    async def delete_task(
        self,
        task_id: str | None = None,
        task_name: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Task:
        trace = self._tracer.trace(trace_id) if self._tracer else None
        async with trace.span(
            parent_id=parent_span_id,
            name="delete_task",
            input={"task_id": task_id, "task_name": task_name},
        ) as span:
            heartbeat_if_in_workflow("delete task")
            if not task_id and not task_name:
                raise ValueError("Either task_id or task_name must be provided.")
            if task_id:
                task_model = await self._agentex_client.tasks.delete(task_id=task_id)
            elif task_name:
                task_model = await self._agentex_client.tasks.delete_by_name(task_name=task_name)
            else:
                raise ValueError("Either task_id or task_name must be provided.")
            if span:
                span.output = task_model.model_dump()
            return task_model
