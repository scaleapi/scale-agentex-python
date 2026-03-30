from __future__ import annotations

from agentex import AsyncAgentex
from agentex.types.task import Task
from agentex.types.shared import DeleteResponse
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import heartbeat_if_in_workflow
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.task_retrieve_response import TaskRetrieveResponse
from agentex.types.task_query_workflow_response import TaskQueryWorkflowResponse
from agentex.types.task_retrieve_by_name_response import TaskRetrieveByNameResponse

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
    ) -> TaskRetrieveResponse | TaskRetrieveByNameResponse:
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
    ) -> Task | DeleteResponse:
        trace = self._tracer.trace(trace_id) if self._tracer else None
        if trace is None:
            # Handle case without tracing
            response = await self._agentex_client.tasks.delete(task_id)
            return Task(**response.model_dump())

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

    async def cancel_task(
        self,
        task_id: str,
        reason: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Task:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="cancel_task",
            input={"task_id": task_id, "reason": reason},
        ) as span:
            heartbeat_if_in_workflow("cancel task")
            task_model = await self._agentex_client.tasks.cancel(task_id=task_id, reason=reason)
            if span:
                span.output = task_model.model_dump()
            return task_model

    async def complete_task(
        self,
        task_id: str,
        reason: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Task:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="complete_task",
            input={"task_id": task_id, "reason": reason},
        ) as span:
            heartbeat_if_in_workflow("complete task")
            task_model = await self._agentex_client.tasks.complete(task_id=task_id, reason=reason)
            if span:
                span.output = task_model.model_dump()
            return task_model

    async def fail_task(
        self,
        task_id: str,
        reason: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Task:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="fail_task",
            input={"task_id": task_id, "reason": reason},
        ) as span:
            heartbeat_if_in_workflow("fail task")
            task_model = await self._agentex_client.tasks.fail(task_id=task_id, reason=reason)
            if span:
                span.output = task_model.model_dump()
            return task_model

    async def terminate_task(
        self,
        task_id: str,
        reason: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Task:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="terminate_task",
            input={"task_id": task_id, "reason": reason},
        ) as span:
            heartbeat_if_in_workflow("terminate task")
            task_model = await self._agentex_client.tasks.terminate(task_id=task_id, reason=reason)
            if span:
                span.output = task_model.model_dump()
            return task_model

    async def timeout_task(
        self,
        task_id: str,
        reason: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Task:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="timeout_task",
            input={"task_id": task_id, "reason": reason},
        ) as span:
            heartbeat_if_in_workflow("timeout task")
            task_model = await self._agentex_client.tasks.timeout(task_id=task_id, reason=reason)
            if span:
                span.output = task_model.model_dump()
            return task_model

    async def update_task(
        self,
        task_id: str | None = None,
        task_name: str | None = None,
        task_metadata: dict[str, object] | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Task:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="update_task",
            input={"task_id": task_id, "task_name": task_name, "task_metadata": task_metadata},
        ) as span:
            heartbeat_if_in_workflow("update task")
            if not task_id and not task_name:
                raise ValueError("Either task_id or task_name must be provided.")
            if task_id:
                task_model = await self._agentex_client.tasks.update_by_id(task_id=task_id, task_metadata=task_metadata)
            elif task_name:
                task_model = await self._agentex_client.tasks.update_by_name(
                    task_name=task_name, task_metadata=task_metadata
                )
            else:
                raise ValueError("Either task_id or task_name must be provided.")
            if span:
                span.output = task_model.model_dump()
            return task_model

    async def query_workflow(
        self,
        task_id: str,
        query_name: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> TaskQueryWorkflowResponse:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="query_workflow",
            input={"task_id": task_id, "query_name": query_name},
        ) as span:
            heartbeat_if_in_workflow("query workflow")
            result = await self._agentex_client.tasks.query_workflow(query_name=query_name, task_id=task_id)
            if span:
                span.output = result
            return result
