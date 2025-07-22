from typing import Any, Dict

from agentex import AsyncAgentex
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.state import State
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class StateService:
    def __init__(
        self, agentex_client: AsyncAgentex, tracer: AsyncTracer
    ):
        self._agentex_client = agentex_client
        self._tracer = tracer

    async def create_state(
        self,
        task_id: str,
        agent_id: str,
        state: dict[str, Any],
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> State:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="create_state",
            input={"task_id": task_id, "agent_id": agent_id, "state": state},
        ) as span:
            state_model = await self._agentex_client.states.create(
                task_id=task_id,
                agent_id=agent_id,
                state=state,
            )
            if span:
                span.output = state_model.model_dump()
            return state_model

    async def get_state(
        self,
        state_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> State | None:
        trace = self._tracer.trace(trace_id) if self._tracer else None
        async with trace.span(
            parent_id=parent_span_id,
            name="get_state",
            input={
                "state_id": state_id,
                "task_id": task_id,
                "agent_id": agent_id,
            },
        ) as span:
            if state_id:
                state = await self._agentex_client.states.retrieve(state_id=state_id)
            elif task_id and agent_id:
                states = await self._agentex_client.states.list(
                    task_id=task_id,
                    agent_id=agent_id,
                )
                state = states[0] if states else None
            else:
                raise ValueError(
                    "Must provide either state_id or both task_id and agent_id"
                )
            if span:
                span.output = state.model_dump() if state else None
            return state

    async def update_state(
        self,
        state_id: str,
        task_id: str,
        agent_id: str,
        state: Dict[str, object],
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> State:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="update_state",
            input={
                "state_id": state_id,
                "task_id": task_id,
                "agent_id": agent_id,
                "state": state,
            },
        ) as span:
            state_model = await self._agentex_client.states.update(
                state_id=state_id,
                task_id=task_id,
                agent_id=agent_id,
                state=state,
            )
            if span:
                span.output = state_model.model_dump()
            return state_model

    async def delete_state(
        self,
        state_id: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> State:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="delete_state",
            input={"state_id": state_id},
        ) as span:
            state = await self._agentex_client.states.delete(state_id)
            if span:
                span.output = state.model_dump()
            return state
