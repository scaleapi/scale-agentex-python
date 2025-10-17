from __future__ import annotations

from typing import override

from temporalio import workflow
from project.state_machines.deep_research import DeepResearchData, DeepResearchState

from agentex.lib.utils.logging import make_logger
from agentex.lib.sdk.state_machine import StateMachine, StateWorkflow

logger = make_logger(__name__)

class WaitingForUserInputWorkflow(StateWorkflow):
    @override
    async def execute(self, state_machine: StateMachine, state_machine_data: DeepResearchData | None = None) -> str:
        logger.info("ActorWaitingForUserInputWorkflow: waiting for user input...")
        def condition():
            current_state = state_machine.get_current_state()
            return current_state != DeepResearchState.WAITING_FOR_USER_INPUT
        await workflow.wait_condition(condition)
        return state_machine.get_current_state() 