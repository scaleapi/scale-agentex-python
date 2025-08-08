# Creator Agent - Generates and revises content based on requests and feedback

import json
import os
from typing import List

from agentex.lib import adk
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.fastacp import AgenticACPConfig
from agentex.lib.types.acp import CancelTaskParams, CreateTaskParams, SendEventParams
from agentex.lib.types.llm_messages import (
    AssistantMessage,
    LLMConfig,
    Message,
    SystemMessage,
    UserMessage,
)
from agentex.types.text_content import TextContent
from agentex.lib.utils.logging import make_logger

import sys
from pathlib import Path

# Add the current directory to the Python path to enable imports
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from models import CreatorRequest, CreatorResponse
from agentex.lib.utils.model_utils import BaseModel

logger = make_logger(__name__)

# Create an ACP server with base configuration
acp = FastACP.create(
    acp_type="agentic",
    config=AgenticACPConfig(
        type="base",
    ),
)


class CreatorState(BaseModel):
    messages: List[Message]
    creation_history: List[dict] = []

@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    """Initialize the creator agent state."""
    logger.info(f"Creator task created: {params.task.id}")
    
    # Initialize state with system message
    system_message = SystemMessage(
        content="""You are a skilled content creator and writer. Your job is to generate and revise high-quality content based on requests and feedback.

Your responsibilities:
1. Create engaging, original content based on user requests
2. Follow all specified rules and requirements precisely
3. Revise content based on feedback while maintaining quality
4. Ensure content meets all specified criteria

When creating content:
- Be creative and engaging while staying on topic
- Follow all rules strictly
- Maintain appropriate tone and style
- Focus on quality and clarity

When revising content:
- Address all feedback points thoroughly
- Maintain the core message while making improvements
- Ensure all rules are still followed after revision

Return ONLY the content itself, no explanations or metadata."""
    )
    
    state = CreatorState(messages=[system_message])
    await adk.state.create(task_id=params.task.id, agent_id=params.agent.id, state=state)
    
    await adk.messages.create(
        task_id=params.task.id,
        content=TextContent(
            author="agent",
            content="✨ **Creator Agent** - Content Generation & Revision\n\nI specialize in creating and revising high-quality content based on your requests.\n\nFor content creation, send:\n```json\n{\n  \"request\": \"Your content request\",\n  \"rules\": [\"Rule 1\", \"Rule 2\"]\n}\n```\n\nFor content revision, send:\n```json\n{\n  \"content\": \"Original content\",\n  \"feedback\": \"Feedback to address\",\n  \"rules\": [\"Rule 1\", \"Rule 2\"]\n}\n```\n\nReady to create amazing content! 🚀",
        ),
    )


@acp.on_task_event_send
async def handle_event_send(params: SendEventParams):
    """Handle content creation and revision requests."""
    
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
    
    # Echo back the message (if from user)
    if params.event.content.author == "user":
        await adk.messages.create(task_id=params.task.id, content=params.event.content)
    
    # Check if OpenAI API key is available
    if not os.environ.get("OPENAI_API_KEY"):
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content="❌ OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.",
            ),
        )
        return
    
    content = params.event.content.content
    
    try:
        # Parse the JSON request
        try:
            request_data = json.loads(content)
        except json.JSONDecodeError:
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content="❌ Please provide a valid JSON request with 'request', 'current_draft', and 'feedback' fields.",
                ),
            )
            return
        
        # Validate required fields
        if "request" not in request_data:
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content="❌ Missing required field: 'request'",
                ),
            )
            return
        
        # Parse and validate request using Pydantic
        try:
            creator_request = CreatorRequest.model_validate(request_data)
        except ValueError as e:
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content=f"❌ Invalid request format: {e}",
                ),
            )
            return
        
        user_request = creator_request.request
        current_draft = creator_request.current_draft
        feedback = creator_request.feedback
        orchestrator_task_id = creator_request.orchestrator_task_id
        
        # Get current state
        task_state = await adk.state.get_by_task_and_agent(task_id=params.task.id, agent_id=params.agent.id)
        state = CreatorState.model_validate(task_state.state)
        
        # Add this request to history
        state.creation_history.append({
            "request": user_request,
            "current_draft": current_draft,
            "feedback": feedback,
            "is_revision": bool(current_draft)
        })
        
        # Create content generation prompt
        if current_draft and feedback:
            # This is a revision request
            user_message_content = f"""Please revise the following content based on the feedback provided:

ORIGINAL REQUEST: {user_request}

CURRENT DRAFT:
{current_draft}

FEEDBACK TO ADDRESS:
{chr(10).join(f'- {item}' for item in feedback)}

Please provide a revised version that addresses all the feedback while maintaining the quality and intent of the original request."""
            
            status_message = f"🔄 **Revising Content** (Iteration {len(state.creation_history)})\n\nRevising based on {len(feedback)} feedback point(s)..."
            
        else:
            # This is an initial creation request
            user_message_content = f"""Please create content for the following request:

{user_request}

Provide high-quality, engaging content that fulfills this request."""
            
            status_message = f"✨ **Creating New Content**\n\nGenerating content for: {user_request}"
        
        # Send status update
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=status_message,
            ),
        )
        
        # Add user message to conversation
        state.messages.append(UserMessage(content=user_message_content))
        
        # Generate content using LLM
        chat_completion = await adk.providers.litellm.chat_completion(
            llm_config=LLMConfig(model="gpt-4o-mini", messages=state.messages),
            trace_id=params.task.id,
        )
        
        if not chat_completion.choices or not chat_completion.choices[0].message:
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content="❌ Failed to generate content. Please try again.",
                ),
            )
            return
        
        generated_content = chat_completion.choices[0].message.content or ""
        
        # Add assistant response to conversation
        state.messages.append(AssistantMessage(content=generated_content))
        
        # Send the generated content back to this task
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=generated_content,
            ),
        )
        
        # Also send the result back to the orchestrator agent if this request came from another agent
        if params.event.content.author == "agent" and orchestrator_task_id:
            try:
                # Send result back to orchestrator using Pydantic model
                result_data = CreatorResponse(
                    content=generated_content,
                    task_id=params.task.id
                ).model_dump()
                
                await adk.acp.send_event(
                    agent_name="ab090-orchestrator-agent",
                    task_id=orchestrator_task_id,  # Use the orchestrator's original task ID
                    content=TextContent(
                        author="agent",
                        content=json.dumps(result_data)
                    )
                )
                logger.info(f"Sent result back to orchestrator for task {orchestrator_task_id}")
                
            except Exception as e:
                logger.error(f"Failed to send result to orchestrator: {e}")
        
        # Update state
        await adk.state.update(
            state_id=task_state.id,
            task_id=params.task.id,
            agent_id=params.agent.id,
            state=state,
            trace_id=params.task.id,
        )
        
        logger.info(f"Generated content for task {params.task.id}: {len(generated_content)} characters")
        
    except Exception as e:
        logger.error(f"Error in content creation: {e}")
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=f"❌ Error creating content: {e}",
            ),
        )


@acp.on_task_cancel
async def handle_task_cancel(params: CancelTaskParams):
    """Handle task cancellation."""
    logger.info(f"Creator task cancelled: {params.task.id}")

