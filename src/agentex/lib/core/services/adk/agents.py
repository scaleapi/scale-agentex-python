from typing import Optional

from agentex import AsyncAgentex
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.agent import Agent
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import heartbeat_if_in_workflow

logger = make_logger(__name__)


class AgentsService:
    def __init__(
        self,
        agentex_client: AsyncAgentex,
        tracer: AsyncTracer,
    ):
        self._agentex_client = agentex_client
        self._tracer = tracer

    async def get_agent(
        self,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
    ) -> Agent:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="get_agent",
            input={"agent_id": agent_id, "agent_name": agent_name},
        ) as span:
            heartbeat_if_in_workflow("get agent")
            if agent_id:
                agent = await self._agentex_client.agents.retrieve(agent_id=agent_id)
            elif agent_name:
                agent = await self._agentex_client.agents.retrieve_by_name(agent_name=agent_name)
            else:
                raise ValueError("Either agent_id or agent_name must be provided")
            if span:
                span.output = agent.model_dump()
            return agent
