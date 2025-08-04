from typing import override
from temporalio import workflow
from agentex.lib import adk
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.types.acp import CreateTaskParams, SendEventParams
from agentex.lib.sdk.state_machine.state import State
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.utils.logging import make_logger

from state_machines.deep_research import (
    DeepResearchStateMachine, 
    DeepResearchState, 
    DeepResearchData
)
from workflows.deep_research.triage import TriageWorkflow
from workflows.deep_research.clarifying import ClarifyingWorkflow
from workflows.deep_research.instruction_builder import InstructionBuilderWorkflow
from workflows.deep_research.research import ResearchWorkflow
from workflows.deep_research.waiting import WaitingForInputWorkflow

environment_variables = EnvironmentVariables.refresh()
logger = make_logger(__name__)

# Use default values if environment variables are not set
WORKFLOW_NAME = environment_variables.WORKFLOW_NAME or "deep-research-workflow"
AGENT_NAME = environment_variables.AGENT_NAME or "Deep Research Agent"

@workflow.defn(name="deep-research-workflow")
class DeepResearchWorkflow(BaseWorkflow):
    def __init__(self):
        super().__init__(display_name=AGENT_NAME)
        self.state_machine = DeepResearchStateMachine(
            initial_state=DeepResearchState.WAITING_FOR_INPUT,
            states=[
                State(name=DeepResearchState.TRIAGE, workflow=TriageWorkflow()),
                State(name=DeepResearchState.CLARIFYING, workflow=ClarifyingWorkflow()),
                State(name=DeepResearchState.INSTRUCTION_BUILDING, workflow=InstructionBuilderWorkflow()),
                State(name=DeepResearchState.RESEARCHING, workflow=ResearchWorkflow()),
                State(name=DeepResearchState.WAITING_FOR_INPUT, workflow=WaitingForInputWorkflow()),
            ],
            state_machine_data=DeepResearchData(),
            trace_transitions=True
        )
    
    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    @override
    async def on_task_event_send(self, params: SendEventParams):
        data = self.state_machine.get_state_machine_data()
        current_state = self.state_machine.get_current_state()
        
        logger.info(f"WorkflowSignal: Received event in state {current_state}")
        logger.info(f"WorkflowSignal: Event content: {params.event.content.content}")
        logger.info(f"WorkflowSignal: Current clarification_questions: {len(data.clarification_questions) if data.clarification_questions else 0}")
        logger.info(f"WorkflowSignal: Current clarification_answers: {len(data.clarification_answers) if data.clarification_answers else 0}")
        
        if current_state == DeepResearchState.WAITING_FOR_INPUT:
            if not data.original_query:
                # First message - set up query and go to triage
                logger.info("WorkflowSignal: First message received, setting up initial query")
                data.original_query = params.event.content.content
                data.task_id = params.task.id
                
                # Start a tracing span
                data.current_span = await adk.tracing.start_span(
                    trace_id=params.task.id,
                    name="Deep Research Session",
                    input={
                        "task_id": params.task.id,
                        "query": params.event.content.content,
                    }
                )
                
                logger.info("WorkflowSignal: Transitioning to TRIAGE")
                await self.state_machine.transition(DeepResearchState.TRIAGE)
            elif data.clarification_questions and not data.enriched_instructions:
                # User is responding to clarification questions
                logger.info("WorkflowSignal: Received response to clarification questions")
                # Store the comprehensive response - user may answer multiple questions in one message
                data.clarification_answers = [params.event.content.content]
                logger.info(f"WorkflowSignal: Clarification response stored: {params.event.content.content}")
                
                # Proceed to instruction building with the user's response
                logger.info("WorkflowSignal: Transitioning to INSTRUCTION_BUILDING with clarification response")
                await self.state_machine.transition(DeepResearchState.INSTRUCTION_BUILDING)
            else:
                # Follow-up question on existing research
                logger.info("WorkflowSignal: No clarification questions found, treating as follow-up message")
                data.agent_messages.append({
                    "role": "user",
                    "content": f"Follow-up: {params.event.content.content}"
                })
                logger.info("WorkflowSignal: Transitioning to RESEARCHING")
                await self.state_machine.transition(DeepResearchState.RESEARCHING)
    
    @workflow.run
    @override
    async def on_task_create(self, params: CreateTaskParams):
        self.state_machine.set_task_id(params.task.id)
        data = self.state_machine.get_state_machine_data()
        data.task_id = params.task.id
        await self.state_machine.run()