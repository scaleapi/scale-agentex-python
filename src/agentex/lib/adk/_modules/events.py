from datetime import timedelta

from temporalio.common import RetryPolicy

from agentex import AsyncAgentex
from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.services.adk.events import EventsService
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.temporal.activities.adk.events_activities import (
    EventsActivityName,
    GetEventParams,
    ListEventsParams,
)
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.event import Event
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import in_temporal_workflow

logger = make_logger(__name__)

# Default retry policy for all events operations
DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


class EventsModule:
    """
    Module for managing events in Agentex.
    Provides high-level async methods for retrieving and listing events.
    """

    def __init__(
        self,
        events_service: EventsService | None = None,
    ):
        if events_service is None:
            agentex_client = create_async_agentex_client()
            tracer = AsyncTracer(agentex_client)
            self._events_service = EventsService(
                agentex_client=agentex_client, tracer=tracer
            )
        else:
            self._events_service = events_service

    async def get(
        self,
        event_id: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> Event | None:
        """
        Get an event by ID.

        Args:
            event_id (str): The ID of the event.
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            Optional[Event]: The event if found, None otherwise.
        """
        params = GetEventParams(
            event_id=event_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=EventsActivityName.GET_EVENT,
                request=params,
                response_type=Event,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._events_service.get_event(
                event_id=event_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def list_events(
        self,
        task_id: str,
        agent_id: str,
        last_processed_event_id: str | None = None,
        limit: int | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> list[Event]:
        """
        List events for a specific task and agent.

        Args:
            task_id (str): The ID of the task.
            agent_id (str): The ID of the agent.
            last_processed_event_id (Optional[str]): Optional event ID to get events after this ID.
            limit (Optional[int]): Optional limit on number of results.
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            List[Event]: List of events ordered by sequence_id.
        """
        params = ListEventsParams(
            task_id=task_id,
            agent_id=agent_id,
            last_processed_event_id=last_processed_event_id,
            limit=limit,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=EventsActivityName.LIST_EVENTS,
                request=params,
                response_type=list[Event],
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._events_service.list_events(
                task_id=task_id,
                agent_id=agent_id,
                last_processed_event_id=last_processed_event_id,
                limit=limit,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )
