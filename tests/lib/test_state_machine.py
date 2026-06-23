from __future__ import annotations

from typing import override
from unittest.mock import AsyncMock, patch

from agentex.lib.sdk.state_machine import State, StateMachine, StateWorkflow
from agentex.lib.utils.model_utils import BaseModel


class ExampleData(BaseModel):
    value: int = 0


class InitialWorkflow(StateWorkflow):
    transitions = ["next"]

    @override
    async def execute(self, state_machine, state_machine_data=None):
        return "next"


class NextWorkflow(StateWorkflow):
    transitions = ["initial"]

    @override
    async def execute(self, state_machine, state_machine_data=None):
        return "initial"


class ExampleStateMachine(StateMachine[ExampleData]):
    @override
    async def terminal_condition(self):
        return False


def _make_state_machine() -> ExampleStateMachine:
    return ExampleStateMachine(
        initial_state="initial",
        states=[
            State(name="initial", workflow=InitialWorkflow()),
            State(name="next", workflow=NextWorkflow()),
        ],
        task_id="task-123",
        state_machine_data=ExampleData(value=1),
        trace_transitions=True,
    )


async def test_reset_to_initial_state_skips_end_span_when_start_span_fails_open():
    state_machine = _make_state_machine()
    await state_machine.transition("next")

    with patch(
        "agentex.lib.sdk.state_machine.state_machine.adk.tracing.start_span",
        new=AsyncMock(return_value=None),
    ) as start_span, patch(
        "agentex.lib.sdk.state_machine.state_machine.adk.tracing.end_span",
        new=AsyncMock(),
    ) as end_span:
        await state_machine.reset_to_initial_state()

    assert state_machine.get_current_state() == "initial"
    start_span.assert_awaited_once_with(
        trace_id="task-123",
        name="state_transition_reset",
        input={"input_state": "next"},
    )
    end_span.assert_not_awaited()
