import asyncio
from typing import override

from temporalio import workflow

from agentex.lib import adk
from agentex.lib.types.acp import CreateTaskParams, SendEventParams
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.sdk.state_machine.state import State

from state_machines.deep_research import DeepResearchStateMachine, DeepResearchState, DeepResearchData
from workflows.deep_research.clarify_user_query import ClarifyUserQueryWorkflow
from workflows.deep_research.waiting_for_user_input import WaitingForUserInputWorkflow
from workflows.deep_research.performing_deep_research import PerformingDeepResearchWorkflow

environment_variables = EnvironmentVariables.refresh()

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")


logger = make_logger(__name__)

@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class At020StateMachineWorkflow(BaseWorkflow):
    """
    Minimal async workflow template for AgentEx Temporal agents.
    """
    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self.state_machine = DeepResearchStateMachine(
            initial_state=DeepResearchState.WAITING_FOR_USER_INPUT,
            states=[
                State(name=DeepResearchState.CLARIFYING_USER_QUERY, workflow=ClarifyUserQueryWorkflow()),
                State(name=DeepResearchState.WAITING_FOR_USER_INPUT, workflow=WaitingForUserInputWorkflow()),
                State(name=DeepResearchState.PERFORMING_DEEP_RESEARCH, workflow=PerformingDeepResearchWorkflow()),
            ],
            state_machine_data=DeepResearchData(),
            trace_transitions=True
        )

    @override
    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        deep_research_data = self.state_machine.get_state_machine_data()
        task = params.task
        message = params.event.content

        # If waiting for user input, handle the message
        if self.state_machine.get_current_state() == DeepResearchState.WAITING_FOR_USER_INPUT:
            if not deep_research_data.user_query:
                # First time - initialize research data
                deep_research_data.user_query = message.content
                deep_research_data.current_turn += 1

                if not deep_research_data.current_span:
                    deep_research_data.current_span = await adk.tracing.start_span(
                        trace_id=task.id,
                        name=f"Turn {deep_research_data.current_turn}",
                        input={
                            "task_id": task.id,
                            "message": message.content,
                        }
                    )
            else:
                # Check if we're in the middle of follow-up questions
                if deep_research_data.n_follow_up_questions_to_ask > 0:
                    # User is responding to a follow-up question
                    deep_research_data.follow_up_responses.append(message.content)
                    
                    # Add the Q&A to the agent input list as context
                    if deep_research_data.follow_up_questions:
                        last_question = deep_research_data.follow_up_questions[-1]
                        qa_context = f"Q: {last_question}\nA: {message.content}"
                        deep_research_data.agent_input_list.append({
                            "role": "user",
                            "content": qa_context
                        })
                else:
                    # User is asking a new follow-up question about the same research topic
                    # Add the user's follow-up question to the agent input list as context
                    if deep_research_data.agent_input_list:
                        # Add user's follow-up question to the conversation
                        deep_research_data.agent_input_list.append({
                            "role": "user", 
                            "content": f"Additional question: {message.content}"
                        })
                    else:
                        # Initialize agent input list with the follow-up question
                        deep_research_data.agent_input_list = [{
                            "role": "user", 
                            "content": f"Original query: {deep_research_data.user_query}\nAdditional question: {message.content}"
                        }]
                
                deep_research_data.current_turn += 1

                if not deep_research_data.current_span:
                    deep_research_data.current_span = await adk.tracing.start_span(
                        trace_id=task.id,
                        name=f"Turn {deep_research_data.current_turn}",
                        input={
                            "task_id": task.id,
                            "message": message.content,
                        }
                    )

            # Always go to clarifying user query to ask follow-up questions
            # This ensures we gather more context before doing deep research
            await self.state_machine.transition(DeepResearchState.CLARIFYING_USER_QUERY)
        
        # Echo back the user's message
        await adk.messages.create(
            task_id=task.id,
            content=TextContent(
                author="user",
                content=message.content,
            ),
            trace_id=task.id,
            parent_span_id=deep_research_data.current_span.id if deep_research_data.current_span else None,
        )

    @override
    @workflow.run
    async def on_task_create(self, params: CreateTaskParams) -> None:
        task = params.task

        self.state_machine.set_task_id(task.id)
        deep_research_data = self.state_machine.get_state_machine_data()
        deep_research_data.task_id = task.id

        try:
            await self.state_machine.run()
        except asyncio.CancelledError as error:
            logger.warning(f"Task canceled by user: {task.id}")
            raise error