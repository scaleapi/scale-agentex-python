from enum import Enum
from typing import Optional

from agentex.lib.core.services.adk.agents import AgentsService
from agentex.types.agent import Agent
from temporalio import activity

from agentex.lib.types.tracing import BaseModelWithTraceParams
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class AgentsActivityName(str, Enum):
    GET_AGENT = "get-agent"


class GetAgentParams(BaseModelWithTraceParams):
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None


class AgentsActivities:
    def __init__(self, agents_service: AgentsService):
        self._agents_service = agents_service

    @activity.defn(name=AgentsActivityName.GET_AGENT)
    async def get_agent(self, params: GetAgentParams) -> Agent | None:
        return await self._agents_service.get_agent(
            agent_id=params.agent_id,
            agent_name=params.agent_name,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

