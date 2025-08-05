# Orchestrator Agent - Coordinates the multi-agent content creation workflow

import json

from agentex.lib import adk
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.fastacp import AgenticACPConfig
from agentex.lib.types.acp import CancelTaskParams, CreateTaskParams, SendEventParams
from agentex.types.text_content import TextContent
from agentex.lib.utils.logging import make_logger

import sys
from pathlib import Path

# Add the current directory to the Python path to enable imports
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from state_machines.content_workflow import (
    ContentWorkflowStateMachine, 
    WorkflowData,
    ContentWorkflowState
)
from models import OrchestratorRequest, CreatorResponse, CriticResponse, FormatterResponse

logger = make_logger(__name__)

# Create an ACP server with base configuration
acp = FastACP.create(
    acp_type="agentic",
    config=AgenticACPConfig(
        type="base",
    ),
)

# Store active state machines by task_id
active_workflows: dict[str, ContentWorkflowStateMachine] = {}


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    """Initialize the content workflow state machine when a task is created."""
    logger.info(f"Task created: {params.task.id}")
    
    # Acknowledge task creation
    await adk.messages.create(
        task_id=params.task.id,
        content=TextContent(
            author="agent",
            content="🎭 **Orchestrator Agent** - Content Assembly Line\n\nI coordinate a multi-agent workflow for content creation:\n• **Creator Agent** - Generates content\n• **Critic Agent** - Reviews against rules\n• **Formatter Agent** - Formats final output\n\nSend me a JSON request with:\n```json\n{\n  \"request\": \"Your content request\",\n  \"rules\": [\"Rule 1\", \"Rule 2\"],\n  \"target_format\": \"HTML\"\n}\n```\n\nReady to orchestrate your content creation! 🚀",
        ),
    )


@acp.on_task_event_send
async def handle_event_send(params: SendEventParams):
    """Handle incoming events and coordinate the multi-agent workflow."""
    
    if not params.event.content:
        return
        
    if params.event.content.type != "text":
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content="❌ I can only process text messages.",
            ),
        )
        return
    
    # Echo back the user's message
    if params.event.content.author == "user":
        await adk.messages.create(task_id=params.task.id, content=params.event.content)
    
    content = params.event.content.content
    
    # Check if this is a response from another agent
    if await handle_agent_response(params.task.id, content):
        return
    
    # Otherwise, this is a user request to start a new workflow
    if params.event.content.author == "user":
        await start_content_workflow(params.task.id, content)


async def handle_agent_response(task_id: str, content: str) -> bool:
    """Handle responses from other agents in the workflow. Returns True if this was an agent response."""
    try:
        # Try to parse as JSON (agent responses should be JSON)
        response_data = json.loads(content)
        
        # Check if this is a response from one of our agents
        if "agent" in response_data and "task_id" in response_data:
            agent_name = response_data["agent"]
            
            # Find the corresponding workflow
            workflow = active_workflows.get(task_id)
            if not workflow:
                logger.warning(f"No active workflow found for task {task_id}")
                return True
            
            logger.info(f"Received response from {agent_name} for task {task_id}")
            
            # Handle based on agent type
            if agent_name == "creator":
                try:
                    creator_response = CreatorResponse.model_validate(response_data)
                    await workflow.handle_creator_response(creator_response.content)
                    
                    # Send status update
                    await adk.messages.create(
                        task_id=task_id,
                        content=TextContent(
                            author="agent",
                            content=f"📝 **Creator Output:**\n{creator_response.content}\n\n🔍 Calling critic agent...",
                        ),
                    )
                except ValueError as e:
                    logger.error(f"Invalid creator response format: {e}")
                    return True
                
                # Advance the workflow to the next state
                await advance_workflow(task_id, workflow)
                
            elif agent_name == "critic":
                try:
                    critic_response = CriticResponse.model_validate(response_data)
                    feedback = critic_response.feedback
                    approval_status = critic_response.approval_status
                except ValueError as e:
                    logger.error(f"Invalid critic response format: {e}")
                    return True
                
                # Create the response in the format expected by the state machine
                critic_response = {"feedback": feedback}
                await workflow.handle_critic_response(json.dumps(critic_response))
                
                # Send status update
                if feedback:
                    feedback_text = '\n• '.join(feedback)
                    await adk.messages.create(
                        task_id=task_id,
                        content=TextContent(
                            author="agent",
                            content=f"🎯 **Critic Feedback:**\n• {feedback_text}\n\n📝 Calling creator agent for revision...",
                        ),
                    )
                else:
                    await adk.messages.create(
                        task_id=task_id,
                        content=TextContent(
                            author="agent",
                            content=f"✅ **Content Approved by Critic!**\n\n🎨 Calling formatter agent...",
                        ),
                    )
                
                # Advance the workflow to the next state
                await advance_workflow(task_id, workflow)
                
            elif agent_name == "formatter":
                try:
                    formatter_response = FormatterResponse.model_validate(response_data)
                    formatted_content = formatter_response.formatted_content
                    target_format = formatter_response.target_format
                except ValueError as e:
                    logger.error(f"Invalid formatter response format: {e}")
                    return True
                
                # Create the response in the format expected by the state machine
                formatter_response = {"formatted_content": formatted_content}
                await workflow.handle_formatter_response(json.dumps(formatter_response))
                
                # Workflow completion is handled in handle_formatter_response
                await complete_workflow(task_id, workflow)
                
                # Send final result
                await adk.messages.create(
                    task_id=task_id,
                    content=TextContent(
                        author="agent",
                        content=f"🎉 **Workflow Complete!**\n\nYour content has been successfully created, reviewed, and formatted.\n\n**Final Result ({target_format}):**\n```{target_format.lower()}\n{formatted_content}\n```",
                    ),
                )
                
                # Clean up completed workflow
                if task_id in active_workflows:
                    del active_workflows[task_id]
                    logger.info(f"Cleaned up completed workflow for task {task_id}")
            
            # Continue workflow execution
            if workflow and not await workflow.terminal_condition():
                await advance_workflow(task_id, workflow)
            
            return True
            
    except json.JSONDecodeError:
        # Not a JSON response, might be a user message
        return False
    except Exception as e:
        logger.error(f"Error handling agent response: {e}")
        return True
    
    return False


async def start_content_workflow(task_id: str, content: str):
    """Start a new content creation workflow."""
    try:
        # Parse the user request
        try:
            request_data = json.loads(content)
        except json.JSONDecodeError:
            await adk.messages.create(
                task_id=task_id,
                content=TextContent(
                    author="agent",
                    content="❌ Please provide a valid JSON request with 'request', 'rules', and 'target_format' fields.\n\nExample:\n```json\n{\n  \"request\": \"Write a welcome message\",\n  \"rules\": [\"Under 50 words\", \"Friendly tone\"],\n  \"target_format\": \"HTML\"\n}\n```",
                ),
            )
            return
        
        # Parse and validate request using Pydantic
        try:
            orchestrator_request = OrchestratorRequest.model_validate(request_data)
        except ValueError as e:
            await adk.messages.create(
                task_id=task_id,
                content=TextContent(
                    author="agent",
                    content=f"❌ Invalid request format: {e}",
                ),
            )
            return
        
        user_request = orchestrator_request.request
        rules = orchestrator_request.rules
        target_format = orchestrator_request.target_format
        
        if not isinstance(rules, list):
            await adk.messages.create(
                task_id=task_id,
                content=TextContent(
                    author="agent",
                    content="❌ 'rules' must be a list of strings",
                ),
            )
            return
        
        # Create workflow data
        workflow_data = WorkflowData(
            user_request=user_request,
            rules=rules,
            target_format=target_format
        )
        
        # Create and start the state machine
        workflow = ContentWorkflowStateMachine(task_id=task_id, initial_data=workflow_data)
        active_workflows[task_id] = workflow
        
        # Send acknowledgment
        await adk.messages.create(
            task_id=task_id,
            content=TextContent(
                author="agent",
                content=f"🚀 **Starting Content Workflow**\n\n**Request:** {user_request}\n**Rules:** {len(rules)} rule(s)\n**Target Format:** {target_format}\n\nInitializing multi-agent workflow...",
            ),
        )
        
        # Start the workflow
        await advance_workflow(task_id, workflow)
        logger.info(f"Started content workflow for task {task_id}")
        
    except Exception as e:
        logger.error(f"Error starting workflow: {e}")
        await adk.messages.create(
            task_id=task_id,
            content=TextContent(
                author="agent",
                content=f"❌ Error starting workflow: {e}",
            ),
        )


async def advance_workflow(task_id: str, workflow: ContentWorkflowStateMachine):
    """Advance the workflow to the next state."""
    
    try:
        # Keep advancing until we reach a waiting state or complete
        max_steps = 10  # Prevent infinite loops
        step_count = 0
        
        while step_count < max_steps and not await workflow.terminal_condition():
            current_state = workflow.get_current_state()
            data = workflow.get_state_machine_data()
            logger.info(f"Advancing workflow from state: {current_state} (step {step_count + 1})")
            
            # Execute the current state's workflow
            logger.info(f"About to execute workflow step")
            await workflow.step()
            logger.info(f"Workflow step completed")
            
            new_state = workflow.get_current_state()
            logger.info(f"New state after step: {new_state}")
            
            # Skip redundant status updates since we handle them in response handlers
            # if current_state != new_state:
            #     await send_status_update(task_id, new_state, data)
            
            # Stop advancing if we're in a waiting state (waiting for external response)
            if new_state in [ContentWorkflowState.WAITING_FOR_CREATOR, 
                           ContentWorkflowState.WAITING_FOR_CRITIC, 
                           ContentWorkflowState.WAITING_FOR_FORMATTER]:
                logger.info(f"Workflow paused in waiting state: {new_state}")
                break
                
            step_count += 1
            
        # Check if workflow is complete
        if await workflow.terminal_condition():
            final_state = workflow.get_current_state()
            if final_state == ContentWorkflowState.COMPLETED:
                await complete_workflow(task_id, workflow)
            else:
                await fail_workflow(task_id, workflow)
        elif step_count >= max_steps:
            logger.error(f"Workflow exceeded max steps ({max_steps}), stopping")
            data = workflow.get_state_machine_data()
            data.last_error = f"Workflow exceeded maximum steps ({max_steps})"
            await workflow.transition(ContentWorkflowState.FAILED)
            await fail_workflow(task_id, workflow)
                
    except Exception as e:
        logger.error(f"Error advancing workflow: {e}")
        await adk.messages.create(
            task_id=task_id,
            content=TextContent(
                author="agent",
                content=f"❌ Workflow error: {e}",
            ),
        )


async def send_status_update(task_id: str, state: str, data: WorkflowData):
    """Send status updates to the user based on the current state."""
    
    message = ""
    # Special handling for CREATING state to show feedback
    if state == ContentWorkflowState.CREATING:
        if data.iteration_count > 0 and data.feedback:
            feedback_text = '\n- '.join(data.feedback)
            message = f"🔄 **Revising Content** (Iteration {data.iteration_count + 1})\n\nCritic provided feedback:\n- {feedback_text}\n\nSending back to Creator Agent for revision..."
        else:
            message = f"📝 **Step 1/3: Creating Content** (Iteration {data.iteration_count + 1})\n\nSending request to Creator Agent..."
    else:
        status_messages = {
            ContentWorkflowState.WAITING_FOR_CREATOR: "⏳ Waiting for Creator Agent to generate content...",
            ContentWorkflowState.REVIEWING: f"🔍 **Step 2/3: Reviewing Content** (Iteration {data.iteration_count})\n\nSending draft to Critic Agent for review against {len(data.rules)} rule(s)...",
            ContentWorkflowState.WAITING_FOR_CRITIC: f"⏳ Waiting for Critic Agent to review...\n\n**Draft:**\n{data.current_draft}\n\n**Rules:**\n- {', '.join(data.rules)}",
            ContentWorkflowState.FORMATTING: f"🎨 **Step 3/3: Formatting Content**\n\nSending approved content to Formatter Agent for {data.target_format} formatting...",
            ContentWorkflowState.WAITING_FOR_FORMATTER: "⏳ Waiting for Formatter Agent to format content...",
            ContentWorkflowState.FAILED: f"❌ **Workflow Failed**\n\nError: {data.last_error}",
        }
        message = status_messages.get(state, f"📊 Current state: {state}")
    
    if not message:
        return

    await adk.messages.create(
        task_id=task_id,
        content=TextContent(
            author="agent",
            content=message,
        ),
    )


async def complete_workflow(task_id: str, workflow: ContentWorkflowStateMachine):
    """Handle successful workflow completion."""
    
    data = workflow.get_state_machine_data()
    
    await adk.messages.create(
        task_id=task_id,
        content=TextContent(
            author="agent",
            content=f"✅ **Content Creation Complete!**\n\n🎯 **Original Request:** {data.user_request}\n🔄 **Iterations:** {data.iteration_count}\n📋 **Rules Applied:** {len(data.rules)}\n🎨 **Format:** {data.target_format}\n\n📝 **Final Content:**\n\n{data.final_content}",
        ),
    )
    
    # Clean up
    if task_id in active_workflows:
        del active_workflows[task_id]


async def fail_workflow(task_id: str, workflow: ContentWorkflowStateMachine):
    """Handle workflow failure."""
    
    data = workflow.get_state_machine_data()
    
    await adk.messages.create(
        task_id=task_id,
        content=TextContent(
            author="agent",
            content=f"❌ **Workflow Failed**\n\nAfter {data.iteration_count} iteration(s), the content creation workflow has failed.\n\n**Error:** {data.last_error}\n\nPlease try again with a simpler request or fewer rules.",
        ),
    )
    
    # Clean up
    if task_id in active_workflows:
        del active_workflows[task_id]


@acp.on_task_cancel
async def handle_task_cancel(params: CancelTaskParams):
    """Handle task cancellation."""
    logger.info(f"Orchestrator task cancelled: {params.task.id}")
    
    # Clean up any active workflow
    if params.task.id in active_workflows:
        del active_workflows[params.task.id]
        logger.info(f"Cleaned up cancelled workflow for task {params.task.id}")
