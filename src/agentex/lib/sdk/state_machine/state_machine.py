from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from agentex.lib import adk
from agentex.lib.sdk.state_machine.state import State
from agentex.lib.sdk.state_machine.state_workflow import StateWorkflow
from agentex.lib.utils.model_utils import BaseModel

T = TypeVar("T", bound=BaseModel)


class StateMachine(ABC, Generic[T]):
    def __init__(
        self,
        initial_state: str,
        states: list[State],
        task_id: str | None = None,
        state_machine_data: T | None = None,
        trace_transitions: bool = False,
    ):
        self._task_id = task_id
        self._state_map: dict[str, State] = {state.name: state for state in states}
        self.state_machine_data = state_machine_data
        self._initial_state = initial_state
        self._trace_transitions = trace_transitions

        # Validate that initial state exists
        if initial_state not in self._state_map:
            raise ValueError(f"Initial state '{initial_state}' not found in states")
        self._current_state = self._state_map[initial_state]

    def set_task_id(self, task_id: str):
        self._task_id = task_id

    def get_current_state(self) -> str:
        return self._current_state.name

    def get_current_workflow(self) -> StateWorkflow:
        """
        Get the workflow of the current state.

        Returns:
            The workflow of the current state

        Raises:
            ValueError: If the current state is not found in the state map
        """
        current_state = self._state_map.get(self.get_current_state())
        if not current_state:
            raise ValueError(f"State {self.get_current_state()} not found")
        return current_state.workflow

    async def transition(self, target_state_name: str):
        if not self._state_map.get(target_state_name):
            raise ValueError(f"State {target_state_name} not found")
        self._current_state = self._state_map[target_state_name]

    def get_state_machine_data(self) -> T:
        return self.state_machine_data

    @abstractmethod
    async def terminal_condition(self) -> bool:
        pass

    # Overwrite this if you want to add more logic to the state machine
    async def run(self):
        while not await self.terminal_condition():
            await self.step()

    async def step(self) -> str:
        current_state_name = self.get_current_state()
        current_state = self._state_map.get(current_state_name)

        if self._trace_transitions:
            if self._task_id is None:
                raise ValueError(
                    "Task ID is must be set before tracing can be enabled"
                )
            span = await adk.tracing.start_span(
                trace_id=self._task_id,
                name="state_transition",
                input=self.state_machine_data.model_dump(),
                data={"input_state": current_state_name},
            )

        next_state_name = await current_state.workflow.execute(
            state_machine=self, state_machine_data=self.state_machine_data
        )

        if self._trace_transitions:
            if self._task_id is None:
                raise ValueError(
                    "Task ID is must be set before tracing can be enabled"
                )
            span.output = self.state_machine_data.model_dump()
            span.data["output_state"] = next_state_name
            await adk.tracing.end_span(trace_id=self._task_id, span=span)

        await self.transition(next_state_name)

        return next_state_name

    async def reset_to_initial_state(self):
        """
        Reset the state machine to its initial state.
        """
        if self._trace_transitions:
            if self._task_id is None:
                raise ValueError(
                    "Task ID is must be set before tracing can be enabled"
                )
            span = await adk.tracing.start_span(
                trace_id=self._task_id,
                name="state_transition_reset",
                input={"input_state": self.get_current_state()},
            )

        await self.transition(self._initial_state)

        if self._trace_transitions:
            span.output = {"output_state": self._initial_state}
            await adk.tracing.end_span(trace_id=self._task_id, span=span)

    def dump(self) -> dict[str, Any]:
        """
        Save the current state of the state machine to a serializable dictionary.
        This includes the current state, task_id, state machine data, and initial state.

        Returns:
            Dict[str, Any]: A dictionary containing the serialized state machine state
        """
        return {
            "task_id": self._task_id,
            "current_state": self.get_current_state(),
            "initial_state": self._initial_state,
            "state_machine_data": self.state_machine_data.model_dump(mode="json")
            if self.state_machine_data
            else None,
            "trace_transitions": self._trace_transitions,
        }

    @classmethod
    async def load(cls, data: dict[str, Any], states: list[State]) -> "StateMachine[T]":
        """
        Load a state machine from a previously saved dictionary.

        Args:
            data: The dictionary containing the saved state machine state
            states: List of all possible states

        Returns:
            StateMachine: A new state machine instance restored to the saved state

        Raises:
            ValueError: If the data is invalid or missing required fields
        """
        try:
            task_id = data.get("task_id")
            current_state_name = data.get("current_state")
            initial_state = data.get("initial_state")
            state_machine_data_dict = data.get("state_machine_data")
            trace_transitions = data.get("trace_transitions")

            if initial_state is None:
                raise ValueError("Initial state not found in saved data")

            # Reconstruct the state machine data into its Pydantic model
            state_machine_data = None
            if state_machine_data_dict is not None:
                # Get the actual model type from the class's type parameters
                model_type = cls.__orig_bases__[0].__args__[0]
                state_machine_data = model_type.model_validate(state_machine_data_dict)

            # Create a new instance
            instance = cls(
                initial_state=initial_state,
                states=states,
                task_id=task_id,
                state_machine_data=state_machine_data,
                trace_transitions=trace_transitions,
            )

            # If there's a saved state, transition to it
            if current_state_name:
                await instance.transition(target_state_name=current_state_name)

            return instance
        except Exception as e:
            raise ValueError(f"Failed to restore state machine: {str(e)}") from e
