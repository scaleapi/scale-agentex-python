from enum import Enum

from temporalio import activity

from agentex.lib.core.services.adk.messages import MessagesService
from agentex.types.task_message import TaskMessage
from agentex.types.task_message_content import TaskMessageContent
from agentex.lib.types.tracing import BaseModelWithTraceParams
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class MessagesActivityName(str, Enum):
    CREATE_MESSAGE = "create-message"
    UPDATE_MESSAGE = "update-message"
    CREATE_MESSAGES_BATCH = "create-messages-batch"
    UPDATE_MESSAGES_BATCH = "update-messages-batch"
    LIST_MESSAGES = "list-messages"


class CreateMessageParams(BaseModelWithTraceParams):
    task_id: str
    content: TaskMessageContent
    emit_updates: bool = True


class UpdateMessageParams(BaseModelWithTraceParams):
    task_id: str
    message_id: str
    content: TaskMessageContent


class CreateMessagesBatchParams(BaseModelWithTraceParams):
    task_id: str
    contents: list[TaskMessageContent]
    emit_updates: bool = True


class UpdateMessagesBatchParams(BaseModelWithTraceParams):
    task_id: str
    updates: dict[str, TaskMessageContent]


class ListMessagesParams(BaseModelWithTraceParams):
    task_id: str
    limit: int | None = None


class MessagesActivities:
    def __init__(self, messages_service: MessagesService):
        self._messages_service = messages_service

    @activity.defn(name=MessagesActivityName.CREATE_MESSAGE)
    async def create_message(self, params: CreateMessageParams) -> TaskMessage:
        return await self._messages_service.create_message(
            task_id=params.task_id,
            content=params.content,
            emit_updates=params.emit_updates,
        )

    @activity.defn(name=MessagesActivityName.UPDATE_MESSAGE)
    async def update_message(self, params: UpdateMessageParams) -> TaskMessage:
        return await self._messages_service.update_message(
            task_id=params.task_id,
            message_id=params.message_id,
            content=params.content,
        )

    @activity.defn(name=MessagesActivityName.CREATE_MESSAGES_BATCH)
    async def create_messages_batch(
        self, params: CreateMessagesBatchParams
    ) -> list[TaskMessage]:
        return await self._messages_service.create_messages_batch(
            task_id=params.task_id,
            contents=params.contents,
            emit_updates=params.emit_updates,
        )

    @activity.defn(name=MessagesActivityName.UPDATE_MESSAGES_BATCH)
    async def update_messages_batch(
        self, params: UpdateMessagesBatchParams
    ) -> list[TaskMessage]:
        return await self._messages_service.update_messages_batch(
            task_id=params.task_id,
            updates=params.updates,
        )

    @activity.defn(name=MessagesActivityName.LIST_MESSAGES)
    async def list_messages(self, params: ListMessagesParams) -> list[TaskMessage]:
        return await self._messages_service.list_messages(
            task_id=params.task_id,
            limit=params.limit,
        )
