from enum import Enum
from typing import Any

from temporalio import activity

from agentex.lib.core.services.adk.state import StateService
from agentex.types.state import State
from agentex.lib.types.tracing import BaseModelWithTraceParams
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class StateActivityName(str, Enum):
    CREATE_STATE = "create-state"
    GET_STATE = "get-state"
    UPDATE_STATE = "update-state"
    DELETE_STATE = "delete-state"


class CreateStateParams(BaseModelWithTraceParams):
    task_id: str
    agent_id: str
    state: dict[str, Any]


class GetStateParams(BaseModelWithTraceParams):
    state_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None


class UpdateStateParams(BaseModelWithTraceParams):
    state_id: str
    task_id: str
    agent_id: str
    state: dict[str, Any]


class DeleteStateParams(BaseModelWithTraceParams):
    state_id: str


class StateActivities:
    def __init__(self, state_service: StateService):
        self._state_service = state_service

    @activity.defn(name=StateActivityName.CREATE_STATE)
    async def create_state(self, params: CreateStateParams) -> State:
        return await self._state_service.create_state(
            task_id=params.task_id,
            agent_id=params.agent_id,
            state=params.state,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=StateActivityName.GET_STATE)
    async def get_state(self, params: GetStateParams) -> State | None:
        return await self._state_service.get_state(
            state_id=params.state_id,
            task_id=params.task_id,
            agent_id=params.agent_id,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=StateActivityName.UPDATE_STATE)
    async def update_state(self, params: UpdateStateParams) -> State:
        return await self._state_service.update_state(
            state_id=params.state_id,
            task_id=params.task_id,
            agent_id=params.agent_id,
            state=params.state,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )

    @activity.defn(name=StateActivityName.DELETE_STATE)
    async def delete_state(self, params: DeleteStateParams) -> State:
        return await self._state_service.delete_state(
            state_id=params.state_id,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )
