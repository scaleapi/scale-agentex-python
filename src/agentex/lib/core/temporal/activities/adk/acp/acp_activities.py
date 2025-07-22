from enum import Enum
from typing import Any

from temporalio import activity

from agentex.lib.core.services.adk.acp.acp import ACPService
from agentex.types.event import Event
from agentex.types.task_message import TaskMessage
from agentex.types.task_message_content import TaskMessageContent
from agentex.types.task import Task
from agentex.lib.types.tracing import BaseModelWithTraceParams
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class ACPActivityName(str, Enum):
    TASK_CREATE = "task-create"
    MESSAGE_SEND = "message-send"
    EVENT_SEND = "event-send"
    TASK_CANCEL = "task-cancel"


class TaskCreateParams(BaseModelWithTraceParams):
    name: str | None = None
    agent_id: str | None = None
    agent_name: str | None = None
    params: dict[str, Any] | None = None


class MessageSendParams(BaseModelWithTraceParams):
    agent_id: str | None = None
    agent_name: str | None = None
    task_id: str | None = None
    content: TaskMessageContent


class EventSendParams(BaseModelWithTraceParams):
    agent_id: str | None = None
    agent_name: str | None = None
    task_id: str | None = None
    content: TaskMessageContent


class TaskCancelParams(BaseModelWithTraceParams):
    task_id: str | None = None
    task_name: str | None = None


class ACPActivities:
    def __init__(self, acp_service: ACPService):
        self._acp_service = acp_service

    @activity.defn(name=ACPActivityName.TASK_CREATE)
    async def task_create(self, params: TaskCreateParams) -> Task:
        return await self._acp_service.task_create(
            name=params.name,
            agent_id=params.agent_id,
            agent_name=params.agent_name,
            params=params.params,
        )

    @activity.defn(name=ACPActivityName.MESSAGE_SEND)
    async def message_send(self, params: MessageSendParams) -> TaskMessage:
        return await self._acp_service.message_send(
            agent_id=params.agent_id,
            agent_name=params.agent_name,
            task_id=params.task_id,
            content=params.content,
        )

    @activity.defn(name=ACPActivityName.EVENT_SEND)
    async def event_send(self, params: EventSendParams) -> Event:
        return await self._acp_service.event_send(
            agent_id=params.agent_id,
            agent_name=params.agent_name,
            task_id=params.task_id,
            content=params.content,
        )

    @activity.defn(name=ACPActivityName.TASK_CANCEL)
    async def task_cancel(self, params: TaskCancelParams) -> Task:
        return await self._acp_service.task_cancel(
            task_id=params.task_id,
            task_name=params.task_name,
        )
