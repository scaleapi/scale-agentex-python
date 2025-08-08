import json
import asyncio
from enum import Enum
from typing import Optional
from agentex.lib.utils.model_utils import BaseModel

from agentex.lib import adk
from agentex.lib.sdk.state_machine.state_machine import StateMachine
from agentex.lib.sdk.state_machine.state import State
from agentex.lib.sdk.state_machine.state_workflow import StateWorkflow
from agentex.types.text_content import TextContent
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

# Use adk module for inter-agent communication


class ContentWorkflowState(str, Enum):
    INITIALIZING = "initializing"
    CREATING = "creating"
    WAITING_FOR_CREATOR = "waiting_for_creator"
    REVIEWING = "reviewing"
    WAITING_FOR_CRITIC = "waiting_for_critic"
    FORMATTING = "formatting"
    WAITING_FOR_FORMATTER = "waiting_for_formatter"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowData(BaseModel):
    user_request: str = ""
    rules: list[str] = []
    target_format: str = "text"
    current_draft: str = ""
    feedback: list[str] = []
    final_content: str = ""
    iteration_count: int = 0
    max_iterations: int = 10
    
    # Task tracking for async coordination
    creator_task_id: Optional[str] = None
    critic_task_id: Optional[str] = None
    formatter_task_id: Optional[str] = None
    
    # Response tracking
    pending_response_from: Optional[str] = None
    last_error: Optional[str] = None


class InitializingWorkflow(StateWorkflow):
    async def execute(self, state_machine: "ContentWorkflowStateMachine", state_machine_data: WorkflowData) -> str:
        logger.info("Initializing content workflow")
        return ContentWorkflowState.CREATING


class CreatingWorkflow(StateWorkflow):
    async def execute(self, state_machine: "ContentWorkflowStateMachine", state_machine_data: WorkflowData) -> str:
        logger.info("Starting content creation")
        try:
            # Create task for creator agent
            creator_task = await adk.acp.create_task(agent_name="ab090-creator-agent")
            task_id = creator_task.id
            logger.info(f"Created task ID: {task_id}")
            
            state_machine_data.creator_task_id = task_id
            state_machine_data.pending_response_from = "creator"
            
            # Send request to creator
            request_data = {
                "request": state_machine_data.user_request,
                "current_draft": state_machine_data.current_draft,
                "feedback": state_machine_data.feedback,
                "orchestrator_task_id": state_machine._task_id  # Tell creator which task to respond to
            }
            
            # Send event to creator agent
            await adk.acp.send_event(
                task_id=task_id,
                agent_name="ab090-creator-agent", 
                content=TextContent(author="agent", content=json.dumps(request_data))
            )
            
            logger.info(f"Sent creation request to creator agent, task_id: {task_id}")
            return ContentWorkflowState.WAITING_FOR_CREATOR
            
        except Exception as e:
            logger.error(f"Error in creating workflow: {e}")
            state_machine_data.last_error = str(e)
            return ContentWorkflowState.FAILED


class WaitingForCreatorWorkflow(StateWorkflow):
    async def execute(self, state_machine: "ContentWorkflowStateMachine", state_machine_data: WorkflowData) -> str:
        # This state waits for creator response - transition happens in ACP event handler
        logger.info("Waiting for creator response...")
        
        # Check if workflow should terminate
        if await state_machine.terminal_condition():
            logger.info("Workflow terminated, stopping waiting loop")
            return state_machine.get_current_state()
            
        await asyncio.sleep(1)  # Prevent tight loop, allow other tasks to run
        return ContentWorkflowState.WAITING_FOR_CREATOR


class ReviewingWorkflow(StateWorkflow):
    async def execute(self, state_machine: "ContentWorkflowStateMachine", state_machine_data: WorkflowData) -> str:
        logger.info("Starting content review")
        try:
            # Create task for critic agent
            critic_task = await adk.acp.create_task(agent_name="ab090-critic-agent")
            task_id = critic_task.id
            logger.info(f"Created critic task ID: {task_id}")
            
            state_machine_data.critic_task_id = task_id
            state_machine_data.pending_response_from = "critic"
            
            # Send request to critic
            request_data = {
                    "draft": state_machine_data.current_draft,
                    "rules": state_machine_data.rules,
                    "orchestrator_task_id": state_machine._task_id  # Tell critic which task to respond to
                }
            
            # Send event to critic agent
            await adk.acp.send_event(
                task_id=task_id,
                agent_name="ab090-critic-agent",
                content=TextContent(author="agent", content=json.dumps(request_data))
            )
            
            logger.info(f"Sent review request to critic agent, task_id: {task_id}")
            return ContentWorkflowState.WAITING_FOR_CRITIC
            
        except Exception as e:
            logger.error(f"Error in reviewing workflow: {e}")
            state_machine_data.last_error = str(e)
            return ContentWorkflowState.FAILED


class WaitingForCriticWorkflow(StateWorkflow):
    async def execute(self, state_machine: "ContentWorkflowStateMachine", state_machine_data: WorkflowData) -> str:
        # This state waits for critic response - transition happens in ACP event handler
        logger.info("Waiting for critic response...")
        
        # Check if workflow should terminate
        if await state_machine.terminal_condition():
            logger.info("Workflow terminated, stopping waiting loop")
            return state_machine.get_current_state()
            
        await asyncio.sleep(1)  # Prevent tight loop, allow other tasks to run
        return ContentWorkflowState.WAITING_FOR_CRITIC


class FormattingWorkflow(StateWorkflow):
    async def execute(self, state_machine: "ContentWorkflowStateMachine", state_machine_data: WorkflowData) -> str:
        logger.info("Starting content formatting")
        try:
            # Create task for formatter agent
            formatter_task = await adk.acp.create_task(agent_name="ab090-formatter-agent")
            task_id = formatter_task.id
            logger.info(f"Created formatter task ID: {task_id}")
            
            state_machine_data.formatter_task_id = task_id
            state_machine_data.pending_response_from = "formatter"
            
            # Send request to formatter
            request_data = {
                    "content": state_machine_data.current_draft,  # Fixed field name
                    "target_format": state_machine_data.target_format,
                    "orchestrator_task_id": state_machine._task_id  # Tell formatter which task to respond to
                }
            
            # Send event to formatter agent
            await adk.acp.send_event(
                task_id=task_id,
                agent_name="ab090-formatter-agent",
                content=TextContent(author="agent", content=json.dumps(request_data))
            )
            
            logger.info(f"Sent format request to formatter agent, task_id: {task_id}")
            return ContentWorkflowState.WAITING_FOR_FORMATTER
            
        except Exception as e:
            logger.error(f"Error in formatting workflow: {e}")
            state_machine_data.last_error = str(e)
            return ContentWorkflowState.FAILED


class WaitingForFormatterWorkflow(StateWorkflow):
    async def execute(self, state_machine: "ContentWorkflowStateMachine", state_machine_data: WorkflowData) -> str:
        # This state waits for formatter response - transition happens in ACP event handler
        logger.info("Waiting for formatter response...")
        
        # Check if workflow should terminate
        if await state_machine.terminal_condition():
            logger.info("Workflow terminated, stopping waiting loop")
            return state_machine.get_current_state()
            
        await asyncio.sleep(1)  # Prevent tight loop, allow other tasks to run
        return ContentWorkflowState.WAITING_FOR_FORMATTER


class CompletedWorkflow(StateWorkflow):
    async def execute(self, state_machine: "ContentWorkflowStateMachine", state_machine_data: WorkflowData) -> str:
        logger.info("Content workflow completed successfully")
        return ContentWorkflowState.COMPLETED


class FailedWorkflow(StateWorkflow):
    async def execute(self, state_machine: "ContentWorkflowStateMachine", state_machine_data: WorkflowData) -> str:
        logger.error(f"Content workflow failed: {state_machine_data.last_error}")
        return ContentWorkflowState.FAILED


class ContentWorkflowStateMachine(StateMachine[WorkflowData]):
    def __init__(self, task_id: str | None = None, initial_data: WorkflowData | None = None):
        states = [
            State(name=ContentWorkflowState.INITIALIZING, workflow=InitializingWorkflow()),
            State(name=ContentWorkflowState.CREATING, workflow=CreatingWorkflow()),
            State(name=ContentWorkflowState.WAITING_FOR_CREATOR, workflow=WaitingForCreatorWorkflow()),
            State(name=ContentWorkflowState.REVIEWING, workflow=ReviewingWorkflow()),
            State(name=ContentWorkflowState.WAITING_FOR_CRITIC, workflow=WaitingForCriticWorkflow()),
            State(name=ContentWorkflowState.FORMATTING, workflow=FormattingWorkflow()),
            State(name=ContentWorkflowState.WAITING_FOR_FORMATTER, workflow=WaitingForFormatterWorkflow()),
            State(name=ContentWorkflowState.COMPLETED, workflow=CompletedWorkflow()),
            State(name=ContentWorkflowState.FAILED, workflow=FailedWorkflow()),
        ]
        
        super().__init__(
            initial_state=ContentWorkflowState.INITIALIZING,
            states=states,
            task_id=task_id,
            state_machine_data=initial_data or WorkflowData(),
            trace_transitions=True
        )
    
    async def terminal_condition(self) -> bool:
        current_state = self.get_current_state()
        return current_state in [ContentWorkflowState.COMPLETED, ContentWorkflowState.FAILED]
    
    async def handle_creator_response(self, response_content: str):
        """Handle response from creator agent"""
        try:
            data = self.get_state_machine_data()
            data.current_draft = response_content
            data.pending_response_from = None
            
            # Move to reviewing state
            await self.transition(ContentWorkflowState.REVIEWING)
            logger.info("Received creator response, transitioning to reviewing")
            
        except Exception as e:
            logger.error(f"Error handling creator response: {e}")
            data = self.get_state_machine_data()
            data.last_error = str(e)
            await self.transition(ContentWorkflowState.FAILED)
    
    async def handle_critic_response(self, response_content: str):
        """Handle response from critic agent"""
        try:
            response_data = json.loads(response_content)
            data = self.get_state_machine_data()
            data.feedback = response_data.get("feedback")
            data.pending_response_from = None
            
            if data.feedback:
                # Has feedback, need to revise
                data.iteration_count += 1
                if data.iteration_count >= data.max_iterations:
                    data.last_error = f"Max iterations ({data.max_iterations}) reached"
                    await self.transition(ContentWorkflowState.FAILED)
                else:
                    await self.transition(ContentWorkflowState.CREATING)
                    logger.info(f"Received critic feedback, iteration {data.iteration_count}, transitioning to creating")
            else:
                # No feedback, content approved
                await self.transition(ContentWorkflowState.FORMATTING)
                logger.info("Content approved by critic, transitioning to formatting")
                
        except Exception as e:
            logger.error(f"Error handling critic response: {e}")
            data = self.get_state_machine_data()
            data.last_error = str(e)
            await self.transition(ContentWorkflowState.FAILED)
    
    async def handle_formatter_response(self, response_content: str):
        """Handle response from formatter agent"""
        try:
            response_data = json.loads(response_content)
            data = self.get_state_machine_data()
            data.final_content = response_data.get("formatted_content")
            data.pending_response_from = None
            
            # Move to completed state
            await self.transition(ContentWorkflowState.COMPLETED)
            logger.info("Received formatter response, workflow completed")
            
        except Exception as e:
            logger.error(f"Error handling formatter response: {e}")
            data = self.get_state_machine_data()
            data.last_error = str(e)
            await self.transition(ContentWorkflowState.FAILED)
