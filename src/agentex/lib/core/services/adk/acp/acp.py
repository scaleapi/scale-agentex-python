from typing import Any, cast

from agentex import AsyncAgentex
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import heartbeat_if_in_workflow
from agentex.types.event import Event
from agentex.types.task import Task
from agentex.types.task_message import TaskMessage
from agentex.types.task_message_content import TaskMessageContent
from agentex.types.task_message_content_param import TaskMessageContentParam

logger = make_logger(__name__)


class ACPService:
    def __init__(
        self,
        agentex_client: AsyncAgentex,
        tracer: AsyncTracer,
    ):
        self._agentex_client = agentex_client
        self._tracer = tracer

    async def task_create(
        self,
        name: str | None = None,
        agent_id: str | None = None,
        agent_name: str | None = None,
        params: dict[str, Any] | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Task:
        trace = self._tracer.trace(trace_id=trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="task_create",
            input={
                "name": name,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "params": params,
            },
        ) as span:
            heartbeat_if_in_workflow("task create")
            if agent_name:
                json_rpc_response = await self._agentex_client.agents.rpc_by_name(
                    agent_name=agent_name,
                    method="task/create",
                    params={
                        "name": name,
                        "params": params,
                    },
                )
            elif agent_id:
                json_rpc_response = await self._agentex_client.agents.rpc(
                    agent_id=agent_id,
                    method="task/create",
                    params={
                        "name": name,
                        "params": params,
                    },
                )
            else:
                raise ValueError("Either agent_name or agent_id must be provided")

            task_entry = Task.model_validate(json_rpc_response.result)
            if span:
                span.output = task_entry.model_dump()
            return task_entry

    async def message_send(
        self,
        content: TaskMessageContent,
        agent_id: str | None = None,
        agent_name: str | None = None,
        task_id: str | None = None,
        task_name: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> TaskMessage:
        trace = self._tracer.trace(trace_id=trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="message_send",
            input={
                "agent_id": agent_id,
                "agent_name": agent_name,
                "task_id": task_id,
                "task_name": task_name,
                "message": content,
            },
        ) as span:
            heartbeat_if_in_workflow("message send")
            if agent_name:
                json_rpc_response = await self._agentex_client.agents.rpc_by_name(
                    agent_name=agent_name,
                    method="message/send",
                    params={
                        "task_id": task_id,
                        "content": cast(TaskMessageContentParam, content.model_dump()),
                        "stream": False,
                    },
                )
            elif agent_id:
                json_rpc_response = await self._agentex_client.agents.rpc(
                    agent_id=agent_id,
                    method="message/send",
                    params={
                        "task_id": task_id,
                        "content": cast(TaskMessageContentParam, content.model_dump()),
                        "stream": False,
                    },
                )
            else:
                raise ValueError("Either agent_name or agent_id must be provided")

            task_message = TaskMessage.model_validate(json_rpc_response.result)
            if span:
                span.output = task_message.model_dump()
            return task_message

    async def event_send(
        self,
        content: TaskMessageContent,
        agent_id: str | None = None,
        agent_name: str | None = None,
        task_id: str | None = None,
        task_name: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Event:
        trace = self._tracer.trace(trace_id=trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="event_send",
            input={
                "agent_id": agent_id,
                "agent_name": agent_name,
                "task_id": task_id,
                "content": content,
            },
        ) as span:
            heartbeat_if_in_workflow("event send")
            if agent_name:
                json_rpc_response = await self._agentex_client.agents.rpc_by_name(
                    agent_name=agent_name,
                    method="event/send",
                    params={
                        "task_id": task_id,
                        "content": cast(TaskMessageContentParam, content.model_dump()),
                    },
                )
            elif agent_id:
                json_rpc_response = await self._agentex_client.agents.rpc(
                    agent_id=agent_id,
                    method="event/send",
                    params={
                        "task_id": task_id,
                        "content": cast(TaskMessageContentParam, content.model_dump()),
                    },
                )
            else:
                raise ValueError("Either agent_name or agent_id must be provided")

            event_entry = Event.model_validate(json_rpc_response.result)
            if span:
                span.output = event_entry.model_dump()
            return event_entry

    async def task_cancel(
        self,
        task_id: str | None = None,
        task_name: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Task:
        trace = self._tracer.trace(trace_id=trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="task_cancel",
            input={
                "task_id": task_id,
                "task_name": task_name,
            },
        ) as span:
            heartbeat_if_in_workflow("task cancel")
            if task_name:
                json_rpc_response = await self._agentex_client.agents.rpc_by_name(
                    agent_name=task_name,
                    method="task/cancel",
                    params={
                        "task_name": task_name,
                    },
                )
            elif task_id:
                json_rpc_response = await self._agentex_client.agents.rpc(
                    agent_id=task_id,
                    method="task/cancel",
                    params={
                        "task_id": task_id,
                    },
                )
            else:
                raise ValueError("Either task_name or task_id must be provided")

            task_entry = Task.model_validate(json_rpc_response.result)
            if span:
                span.output = task_entry.model_dump()
            return task_entry
