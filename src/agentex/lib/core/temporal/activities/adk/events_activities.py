from enum import Enum

from temporalio import activity

from agentex.lib.core.services.adk.events import EventsService
from agentex.types.event import Event
from agentex.lib.types.tracing import BaseModelWithTraceParams
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class EventsActivityName(str, Enum):
    GET_EVENT = "get-event"
    LIST_EVENTS = "list-events"


class GetEventParams(BaseModelWithTraceParams):
    event_id: str


class ListEventsParams(BaseModelWithTraceParams):
    task_id: str
    agent_id: str
    last_processed_event_id: str | None = None
    limit: int | None = None


class EventsActivities:
    def __init__(self, events_service: EventsService):
        self._events_service = events_service

    @activity.defn(name=EventsActivityName.GET_EVENT)
    async def get_event(self, params: GetEventParams) -> Event | None:
        return await self._events_service.get_event(
            event_id=params.event_id,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=EventsActivityName.LIST_EVENTS)
    async def list_events(self, params: ListEventsParams) -> list[Event]:
        return await self._events_service.list_events(
            task_id=params.task_id,
            agent_id=params.agent_id,
            last_processed_event_id=params.last_processed_event_id,
            limit=params.limit,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )
