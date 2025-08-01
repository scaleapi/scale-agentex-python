from datetime import timedelta

from temporalio.common import RetryPolicy

from agentex import AsyncAgentex
from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.services.adk.agent_task_tracker import AgentTaskTrackerService
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.temporal.activities.adk.agent_task_tracker_activities import (
    AgentTaskTrackerActivityName,
    GetAgentTaskTrackerByTaskAndAgentParams,
    GetAgentTaskTrackerParams,
    UpdateAgentTaskTrackerParams,
)
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.agent_task_tracker import AgentTaskTracker
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import in_temporal_workflow

logger = make_logger(__name__)

# Default retry policy for all agent task tracker operations
DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


class AgentTaskTrackerModule:
    """
    Module for managing agent task trackers in Agentex.
    Provides high-level async methods for retrieving, filtering, and updating agent task trackers.
    """

    def __init__(
        self,
        agent_task_tracker_service: AgentTaskTrackerService | None = None,
    ):
        if agent_task_tracker_service is None:
            agentex_client = create_async_agentex_client()
            tracer = AsyncTracer(agentex_client)
            self._agent_task_tracker_service = AgentTaskTrackerService(
                agentex_client=agentex_client, tracer=tracer
            )
        else:
            self._agent_task_tracker_service = agent_task_tracker_service

    async def get(
        self,
        tracker_id: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> AgentTaskTracker:
        """
        Get an agent task tracker by ID.

        Args:
            tracker_id (str): The ID of the tracker.
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            AgentTaskTracker: The agent task tracker.
        """
        params = GetAgentTaskTrackerParams(
            tracker_id=tracker_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=AgentTaskTrackerActivityName.GET_AGENT_TASK_TRACKER,
                request=params,
                response_type=AgentTaskTracker,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._agent_task_tracker_service.get_agent_task_tracker(
                tracker_id=tracker_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def get_by_task_and_agent(
        self,
        task_id: str,
        agent_id: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> AgentTaskTracker | None:
        """
        Get an agent task tracker by task ID and agent ID.
        """
        params = GetAgentTaskTrackerByTaskAndAgentParams(
            task_id=task_id,
            agent_id=agent_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=AgentTaskTrackerActivityName.GET_AGENT_TASK_TRACKER_BY_TASK_AND_AGENT,
                request=params,
                response_type=AgentTaskTracker,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._agent_task_tracker_service.get_by_task_and_agent(
                task_id=task_id,
                agent_id=agent_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def update(
        self,
        tracker_id: str,
        last_processed_event_id: str | None = None,
        status: str | None = None,
        status_reason: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> AgentTaskTracker:
        """
        Update an agent task tracker.

        Args:
            tracker_id (str): The ID of the tracker to update.
            request (UpdateAgentTaskTrackerRequest): The update request containing the new values.
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            AgentTaskTracker: The updated agent task tracker.
        """
        params = UpdateAgentTaskTrackerParams(
            tracker_id=tracker_id,
            last_processed_event_id=last_processed_event_id,
            status=status,
            status_reason=status_reason,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=AgentTaskTrackerActivityName.UPDATE_AGENT_TASK_TRACKER,
                request=params,
                response_type=AgentTaskTracker,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._agent_task_tracker_service.update_agent_task_tracker(
                tracker_id=tracker_id,
                last_processed_event_id=last_processed_event_id,
                status=status,
                status_reason=status_reason,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )
