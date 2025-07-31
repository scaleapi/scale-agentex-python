from datetime import timedelta
from typing import Any

from pydantic import BaseModel
from temporalio.common import RetryPolicy

from agentex import AsyncAgentex
from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.services.adk.state import StateService
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.temporal.activities.adk.state_activities import (
    CreateStateParams,
    DeleteStateParams,
    GetStateParams,
    StateActivityName,
    UpdateStateParams,
)
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.state import State
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import in_temporal_workflow

logger = make_logger(__name__)

# Default retry policy for all state operations
DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


class StateModule:
    """
    Module for managing task state in Agentex.
    Provides high-level async methods for creating, retrieving, updating, and deleting state.
    """

    def __init__(
        self,
        state_service: StateService | None = None,
    ):
        if state_service is None:
            agentex_client = create_async_agentex_client()
            tracer = AsyncTracer(agentex_client)
            self._state_service = StateService(
                agentex_client=agentex_client, tracer=tracer
            )
        else:
            self._state_service = state_service

    async def create(
        self,
        task_id: str,
        agent_id: str,
        state: dict[str, Any] | BaseModel,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> State:
        """
        Create a new state for a task and agent.

        Args:
            task_id (str): The ID of the task.
            agent_id (str): The ID of the agent.
            state (Dict[str, Any]): The state to create.
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            State: The created state.
        """
        state_dict = state.model_dump() if isinstance(state, BaseModel) else state
        params = CreateStateParams(
            task_id=task_id,
            agent_id=agent_id,
            state=state_dict,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=StateActivityName.CREATE_STATE,
                request=params,
                response_type=State,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._state_service.create_state(
                task_id=task_id,
                agent_id=agent_id,
                state=state_dict,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def get(
        self,
        state_id: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> State | None:
        """
        Get a state by ID.

        Args:
            state_id (str): The ID of the state.
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            Optional[State]: The state if found, None otherwise.
        """
        params = GetStateParams(
            state_id=state_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=StateActivityName.GET_STATE,
                request=params,
                response_type=State,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._state_service.get_state(
                state_id=state_id,
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
    ) -> State | None:
        """
        Get a state by task and agent ID. A state is uniquely identified by task and the agent that created it.

        Args:
            task_id (str): The ID of the task.
            agent_id (str): The ID of the agent.
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            Optional[State]: The state if found, None otherwise.
        """
        params = GetStateParams(
            task_id=task_id,
            agent_id=agent_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=StateActivityName.GET_STATE,
                request=params,
                response_type=State,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._state_service.get_state(
                task_id=task_id,
                agent_id=agent_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def update(
        self,
        state_id: str,
        task_id: str,
        agent_id: str,
        state: dict[str, Any] | BaseModel,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> State:
        """
        Update a state by ID.

        Args:
            state_id (str): The ID of the state.
            task_id (str): The ID of the task.
            agent_id (str): The ID of the agent.
            state (Dict[str, Any]): The state to update.
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            State: The updated state.
        """
        state_dict = state.model_dump() if isinstance(state, BaseModel) else state
        params = UpdateStateParams(
            state_id=state_id,
            task_id=task_id,
            agent_id=agent_id,
            state=state_dict,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=StateActivityName.UPDATE_STATE,
                request=params,
                response_type=State,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._state_service.update_state(
                state_id=state_id,
                task_id=task_id,
                agent_id=agent_id,
                state=state_dict,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def delete(
        self,
        state_id: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> State:
        """
        Delete a state by ID.

        Args:
            state_id (str): The ID of the state.
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            State: The deleted state.
        """
        params = DeleteStateParams(
            state_id=state_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=StateActivityName.DELETE_STATE,
                request=params,
                response_type=State,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._state_service.delete_state(
                state_id=state_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )
