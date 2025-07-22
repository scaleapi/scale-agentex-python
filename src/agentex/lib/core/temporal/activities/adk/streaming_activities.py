from enum import Enum

from temporalio import activity

from agentex.lib.core.services.adk.streaming import StreamingService
from agentex.lib.types.task_message_updates import TaskMessageUpdate
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.utils.temporal import heartbeat_if_in_workflow

logger = make_logger(__name__)


class StreamingActivityName(str, Enum):
    STREAM_UPDATE = "stream-update"


class StreamUpdateParams(BaseModel):
    update: TaskMessageUpdate


class StreamingActivities:
    """
    Temporal activities for streaming events to clients (ADK pattern).
    """

    def __init__(self, streaming_service: StreamingService):
        self._streaming_service = streaming_service

    @activity.defn(name=StreamingActivityName.STREAM_UPDATE)
    async def stream_update(self, params: StreamUpdateParams) -> TaskMessageUpdate | None:
        heartbeat_if_in_workflow("stream update")
        return await self._streaming_service.stream_update(update=params.update)
