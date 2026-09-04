from __future__ import annotations

from typing import Any, List, cast

from agentex import AsyncAgentex
from agentex.types.task import Task
from agentex.types.event import Event
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import heartbeat_if_in_workflow
from agentex.types.task_message import TaskMessage
from agentex.types.agent_rpc_params import (
    ParamsSendEventRequest as RpcParamsSendEventRequest,
    ParamsCancelTaskRequest as RpcParamsCancelTaskRequest,
)
from agentex.lib.core.tracing.tracer import AsyncTracer
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
        request: dict[str, Any] | None = None,
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
            
            # Extract headers from request; pass-through to agent
            extra_headers = request.get("headers") if request else None
            
            if agent_name:
                json_rpc_response = await self._agentex_client.agents.rpc_by_name(
                    agent_name=agent_name,
                    method="task/create",
                    params={
                        "name": name,
                        "params": params,
                    },
                    extra_headers=extra_headers,
                )
            elif agent_id:
                json_rpc_response = await self._agentex_client.agents.rpc(
                    agent_id=agent_id,
                    method="task/create",
                    params={
                        "name": name,
                        "params": params,
                    },
                    extra_headers=extra_headers,
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
        request: dict[str, Any] | None = None,
    ) -> List[TaskMessage]:
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
            
            # Extract headers from request; pass-through to agent
            extra_headers = request.get("headers") if request else None
            
            if agent_name:
                json_rpc_response = await self._agentex_client.agents.rpc_by_name(
                    agent_name=agent_name,
                    method="message/send",
                    params={
                        "task_id": task_id,
                        "content": cast(TaskMessageContentParam, content.model_dump()),
                        "stream": False,
                    },
                    extra_headers=extra_headers,
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
                    extra_headers=extra_headers,
                )
            else:
                raise ValueError("Either agent_name or agent_id must be provided")

            task_messages: List[TaskMessage] = []
            logger.info("json_rpc_response: %s", json_rpc_response)
            if isinstance(json_rpc_response.result, list):
                for message in json_rpc_response.result:
                    task_message = TaskMessage.model_validate(message)
                    task_messages.append(task_message)
            else:
                task_messages = [TaskMessage.model_validate(json_rpc_response.result)]

            if span:
                span.output = [task_message.model_dump() for task_message in task_messages]
            return task_messages

    async def event_send(
        self,
        content: TaskMessageContent,
        agent_id: str | None = None,
        agent_name: str | None = None,
        task_id: str | None = None,
        task_name: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        request: dict[str, Any] | None = None,
    ) -> Event:
        trace = self._tracer.trace(trace_id=trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="event_send",
            input={
                "agent_id": agent_id,
                "agent_name": agent_name,
                "task_id": task_id,
                "task_name": task_name,
                "content": content,
            },
        ) as span:
            heartbeat_if_in_workflow("event send")
            
            # Extract headers from request; pass-through to agent
            extra_headers = request.get("headers") if request else None
            
            rpc_event_params: RpcParamsSendEventRequest = {
                "task_id": task_id,
                "task_name": task_name,
                "content": cast(TaskMessageContentParam, content.model_dump()),
            }
            if agent_name:
                json_rpc_response = await self._agentex_client.agents.rpc_by_name(
                    agent_name=agent_name,
                    method="event/send",
                    params=rpc_event_params,
                    extra_headers=extra_headers,
                )
            elif agent_id:
                json_rpc_response = await self._agentex_client.agents.rpc(
                    agent_id=agent_id,
                    method="event/send",
                    params=rpc_event_params,
                    extra_headers=extra_headers,
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
        agent_id: str | None = None,
        agent_name: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        request: dict[str, Any] | None = None,
    ) -> Task:
        """
        Cancel a task by sending cancel request to the agent that owns the task.
        
        Args:
            task_id: ID of the task to cancel (passed to agent in params)
            task_name: Name of the task to cancel (passed to agent in params)  
            agent_id: ID of the agent that owns the task
            agent_name: Name of the agent that owns the task
            trace_id: Trace ID for tracing
            parent_span_id: Parent span ID for tracing
            request: Additional request context including headers to forward to the agent
            
        Returns:
            Task entry representing the cancelled task
            
        Raises:
            ValueError: If neither agent_name nor agent_id is provided,
                       or if neither task_name nor task_id is provided
        """
        # Require agent identification
        if not agent_name and not agent_id:
            raise ValueError("Either agent_name or agent_id must be provided to identify the agent that owns the task")
            
        # Require task identification
        if not task_name and not task_id:
            raise ValueError("Either task_name or task_id must be provided to identify the task to cancel")
        trace = self._tracer.trace(trace_id=trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="task_cancel",
            input={
                "task_id": task_id,
                "task_name": task_name,
                "agent_id": agent_id,
                "agent_name": agent_name,
            },
        ) as span:
            heartbeat_if_in_workflow("task cancel")
            
            # Extract headers from request; pass-through to agent
            extra_headers = request.get("headers") if request else None
            
            # Build params for the agent (task identification)
            params: RpcParamsCancelTaskRequest = {}
            if task_id:
                params["task_id"] = task_id
            if task_name:
                params["task_name"] = task_name
            
            # Send cancel request to the correct agent
            if agent_name:
                json_rpc_response = await self._agentex_client.agents.rpc_by_name(
                    agent_name=agent_name,
                    method="task/cancel",
                    params=params,
                    extra_headers=extra_headers,
                )
            else:  # agent_id is provided (validated above)
                assert agent_id is not None
                json_rpc_response = await self._agentex_client.agents.rpc(
                    agent_id=agent_id,
                    method="task/cancel",
                    params=params,
                    extra_headers=extra_headers,
                )

            task_entry = Task.model_validate(json_rpc_response.result)
            if span:
                span.output = task_entry.model_dump()
            return task_entry
