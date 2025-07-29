from datetime import timedelta
from typing import Optional

from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.temporal.activities.adk.agents_activities import AgentsActivityName, GetAgentParams
from temporalio.common import RetryPolicy

from agentex import AsyncAgentex
from agentex.lib.core.services.adk.agents import AgentsService
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.agent import Agent
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import in_temporal_workflow

logger = make_logger(__name__)

DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


class AgentsModule:
    """
    Module for managing agents in Agentex.
    Provides high-level async methods for retrieving, listing, and deleting agents.
    """

    def __init__(
        self,
        agents_service: Optional[AgentsService] = None,
    ):
        if agents_service is None:
            agentex_client = create_async_agentex_client()
            tracer = AsyncTracer(agentex_client)
            self._agents_service = AgentsService(agentex_client=agentex_client, tracer=tracer)
        else:
            self._agents_service = agents_service

    async def get(
        self,
        *,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> Agent:
        """
        Get an agent by ID or name.
        Args:
            agent_id: The ID of the agent to retrieve.
            agent_name: The name of the agent to retrieve.
        Returns:
            The agent entry.
        """
        params = GetAgentParams(
            agent_id=agent_id,
            agent_name=agent_name,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=AgentsActivityName.GET_AGENT,
                request=params,
                response_type=Agent,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._agents_service.get_agent(
                agent_id=agent_id,
                agent_name=agent_name,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )
