from agentex import AsyncAgentex
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.event import Event
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class EventsService:
    def __init__(
        self, agentex_client: AsyncAgentex, tracer: AsyncTracer
    ):
        self._agentex_client = agentex_client
        self._tracer = tracer

    async def get_event(
        self,
        event_id: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> Event | None:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="get_event",
            input={"event_id": event_id},
        ) as span:
            event = await self._agentex_client.events.retrieve(event_id=event_id)
            if span:
                span.output = event.model_dump()
            return event

    async def list_events(
        self,
        task_id: str,
        agent_id: str,
        last_processed_event_id: str | None = None,
        limit: int | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> list[Event]:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="list_events",
            input={
                "task_id": task_id,
                "agent_id": agent_id,
                "last_processed_event_id": last_processed_event_id,
                "limit": limit,
            },
        ) as span:
            events = await self._agentex_client.events.list(
                task_id=task_id,
                agent_id=agent_id,
                last_processed_event_id=last_processed_event_id,
                limit=limit,
            )
            if span:
                span.output = [event.model_dump() for event in events]
            return events
