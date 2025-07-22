import asyncio
from typing import Any, Coroutine, cast

from agentex import AsyncAgentex
from agentex.lib.core.services.adk.streaming import StreamingService
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.lib.types.task_message_updates import StreamTaskMessageFull, TaskMessageUpdate
from agentex.types.task_message import TaskMessage, TaskMessageContent
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import heartbeat_if_in_workflow
from agentex.types.task_message_content_param import TaskMessageContentParam

logger = make_logger(__name__)


class MessagesService:
    def __init__(
        self,
        agentex_client: AsyncAgentex,
        streaming_service: StreamingService,
        tracer: AsyncTracer,
    ):
        self._agentex_client = agentex_client
        self._streaming_service = streaming_service
        self._tracer = tracer

    async def create_message(
        self,
        task_id: str,
        content: TaskMessageContent,
        emit_updates: bool = True,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> TaskMessage:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="create_message",
            input={"task_id": task_id, "message": content},
        ) as span:
            heartbeat_if_in_workflow("create message")
            task_message = await self._agentex_client.messages.create(
                task_id=task_id,
                content=content.model_dump(),
            )
            if emit_updates:
                await self._emit_updates([task_message])
            if span:
                span.output = task_message.model_dump()
            return task_message

    async def update_message(
        self,
        task_id: str,
        message_id: str,
        content: TaskMessageContent,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> TaskMessage:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="update_message",
            input={
                "task_id": task_id,
                "message_id": message_id,
                "message": content,
            },
        ) as span:
            heartbeat_if_in_workflow("update message")
            task_message = await self._agentex_client.messages.update(
                task_id=task_id,
                message_id=message_id,
                content=content.model_dump(),
            )
            if span:
                span.output = task_message.model_dump()
            return task_message

    async def create_messages_batch(
        self,
        task_id: str,
        contents: list[TaskMessageContent],
        emit_updates: bool = True,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> list[TaskMessage]:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="create_messages_batch",
            input={"task_id": task_id, "messages": contents},
        ) as span:
            heartbeat_if_in_workflow("create messages batch")
            task_messages = await self._agentex_client.messages.batch.create(
                task_id=task_id,
                contents=[content.model_dump() for content in contents],
            )
            if emit_updates:
                await self._emit_updates(task_messages)
            if span:
                span.output = [task_message.model_dump() for task_message in task_messages]
            return task_messages

    async def update_messages_batch(
        self,
        task_id: str,
        updates: dict[str, TaskMessageContent],
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> list[TaskMessage]:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="update_messages_batch",
            input={"task_id": task_id, "updates": updates},
        ) as span:
            heartbeat_if_in_workflow("update messages batch")
            task_messages = await self._agentex_client.messages.batch.update(
                task_id=task_id,
                updates={
                    message_id: content.model_dump()
                    for message_id, content in updates.items()
                },
            )
            if span:
                span.output = [task_message.model_dump() for task_message in task_messages]
            return task_messages

    async def list_messages(
        self,
        task_id: str,
        limit: int | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> list[TaskMessage]:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="list_messages",
            input={"task_id": task_id, "limit": limit},
        ) as span:
            heartbeat_if_in_workflow("list messages")
            task_messages = await self._agentex_client.messages.list(
                task_id=task_id,
                limit=limit,
            )
            if span:
                span.output = [task_message.model_dump() for task_message in task_messages]
            return task_messages

    async def _emit_updates(self, task_messages: list[TaskMessage]) -> None:
        stream_update_handlers: list[Coroutine[Any, Any, TaskMessageUpdate | None]] = []
        for task_message in task_messages:
            stream_update_handler = self._streaming_service.stream_update(
                update=StreamTaskMessageFull(
                    type="full",
                    parent_task_message=task_message,
                    content=task_message.content,
                )
            )
            stream_update_handlers.append(stream_update_handler)

        await asyncio.gather(*stream_update_handlers)
