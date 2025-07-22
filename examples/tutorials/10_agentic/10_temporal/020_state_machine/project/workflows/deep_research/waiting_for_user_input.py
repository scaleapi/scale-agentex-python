from typing import override
from agentex.lib.sdk.state_machine import StateWorkflow, StateMachine
from agentex.lib.utils.logging import make_logger
from temporalio import workflow
from state_machines.deep_research import DeepResearchData, DeepResearchState

logger = make_logger(__name__)

class WaitingForUserInputWorkflow(StateWorkflow):
    @override
    async def execute(self, state_machine: StateMachine, state_machine_data: DeepResearchData = None) -> str:
        logger.info("ActorWaitingForUserInputWorkflow: waiting for user input...")
        def condition():
            current_state = state_machine.get_current_state()
            return current_state != DeepResearchState.WAITING_FOR_USER_INPUT
        await workflow.wait_condition(condition)
        return state_machine.get_current_state() 