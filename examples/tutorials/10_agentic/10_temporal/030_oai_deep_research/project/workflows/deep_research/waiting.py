from typing import override
from agentex.lib.sdk.state_machine.state_workflow import StateWorkflow
from agentex.lib.utils.logging import make_logger
from state_machines.deep_research import DeepResearchState
from temporalio import workflow

logger = make_logger(__name__)

class WaitingForInputWorkflow(StateWorkflow):
    @override
    async def execute(self, state_machine, state_machine_data=None):
        logger.info("WaitingForInputWorkflow: waiting for user input...")
        
        def condition():
            current_state = state_machine.get_current_state()
            logger.info(f"WaitingForInputWorkflow: checking condition, current state: {current_state}")
            return current_state != DeepResearchState.WAITING_FOR_INPUT
            
        await workflow.wait_condition(condition)
        final_state = state_machine.get_current_state()
        logger.info(f"WaitingForInputWorkflow: condition met, transitioning to: {final_state}")
        return final_state