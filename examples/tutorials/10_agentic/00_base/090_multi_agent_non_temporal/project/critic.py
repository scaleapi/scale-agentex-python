# Critic Agent - Reviews content drafts against specified rules and provides feedback

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

from models import CriticRequest, CriticResponse
from agentex.lib.utils.model_utils import BaseModel

logger = make_logger(__name__)

# Create an ACP server with base configuration
acp = FastACP.create(
    acp_type="agentic",
    config=AgenticACPConfig(
        type="base",
    ),
)


class CriticState(BaseModel):
    messages: List[Message]
    review_history: List[dict] = []


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    """Initialize the critic agent state."""
    logger.info(f"Critic task created: {params.task.id}")
    
    # Initialize state with system message
    system_message = SystemMessage(
        content="""You are a professional content critic and quality assurance specialist. Your job is to review content against specific rules and provide constructive feedback.

Your responsibilities:
1. Review content against a set of rules
2. Provide specific, actionable feedback for each rule violation
3. Approve content only when all rules are met
4. Be objective and consistent in your reviews

When reviewing content:
- Systematically check the content against each rule
- For each violation, explain clearly why it fails and suggest how to fix it
- If a rule is subjective (e.g., "friendly tone"), provide a brief justification for your assessment
- If all rules are met, provide an empty feedback list

Return ONLY a JSON object in the specified format. Do not include any other text or explanations."""
    )
    
    state = CriticState(messages=[system_message])
    await adk.state.create(task_id=params.task.id, agent_id=params.agent.id, state=state)
    
    await adk.messages.create(
        task_id=params.task.id,
        content=TextContent(
            author="agent",
            content="🔍 **Critic Agent** - Content Quality Assurance\n\nI specialize in reviewing content against specific rules and providing constructive feedback.\n\nSend me a JSON request with:\n```json\n{\n  \"draft\": \"Content to review\",\n  \"rules\": [\"Rule 1\", \"Rule 2\", \"Rule 3\"]\n}\n```\n\nI'll respond with feedback JSON:\n```json\n{\n  \"feedback\": [\"issue1\", \"issue2\"] // or [] if approved\n}\n```\n\nReady to ensure quality! 🎯",
        ),
    )


@acp.on_task_event_send
async def handle_event_send(params: SendEventParams):
    """Handle content review requests."""
    
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
                    content="❌ Please provide a valid JSON request with 'draft' and 'rules' fields.",
                ),
            )
            return
        
        # Validate required fields
        if "draft" not in request_data or "rules" not in request_data:
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content="❌ Missing required fields: 'draft' and 'rules'",
                ),
            )
            return
        
        # Parse and validate request using Pydantic
        try:
            critic_request = CriticRequest.model_validate(request_data)
        except ValueError as e:
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content=f"❌ Invalid request format: {e}",
                ),
            )
            return
        
        draft = critic_request.draft
        rules = critic_request.rules
        orchestrator_task_id = critic_request.orchestrator_task_id
        
        if not isinstance(rules, list):
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content="❌ 'rules' must be a list of strings",
                ),
            )
            return
        
        # Get current state
        task_state = await adk.state.get_by_task_and_agent(task_id=params.task.id, agent_id=params.agent.id)
        state = CriticState.model_validate(task_state.state)
        
        # Add this review to history
        state.review_history.append({
            "draft": draft,
            "rules": rules,
            "timestamp": "now"  # In real implementation, use proper timestamp
        })
        
        # Send status update
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=f"🔍 **Reviewing Content** (Review #{len(state.review_history)})\n\nChecking content against {len(rules)} rules...",
            ),
        )
        
        # Create review prompt
        rules_text = "\n".join([f"{i+1}. {rule}" for i, rule in enumerate(rules)])
        
        user_message_content = f"""Please review the following content against the specified rules and provide feedback:

CONTENT TO REVIEW:
{draft}

RULES TO CHECK:
{rules_text}

Review the content systematically against each rule. For each rule violation:
1. Identify which rule is violated
2. Explain why it violates the rule
3. Suggest how to fix it

If the content meets all rules, return an empty feedback list.

You MUST respond with a JSON object in this exact format:
{{
  "feedback": ["specific issue 1", "specific issue 2", ...] // or [] if all rules are met
}}

Do not include any other text or explanations outside the JSON response."""
        
        # Add user message to conversation
        state.messages.append(UserMessage(content=user_message_content))
        
        # Generate review using LLM
        chat_completion = await adk.providers.litellm.chat_completion(
            llm_config=LLMConfig(model="gpt-4o-mini", messages=state.messages),
            trace_id=params.task.id,
        )
        
        if not chat_completion.choices or not chat_completion.choices[0].message:
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content="❌ Failed to generate review. Please try again.",
                ),
            )
            return
        
        review_response = chat_completion.choices[0].message.content or ""
        
        # Add assistant response to conversation
        state.messages.append(AssistantMessage(content=review_response))
        
        # Parse the review response
        try:
            review_data = json.loads(review_response.strip())
            feedback = review_data.get("feedback", [])
        except json.JSONDecodeError:
            # Fallback if LLM doesn't return valid JSON
            feedback = ["Unable to parse review response"]
        
        # Create result message
        if feedback:
            result_message = f"❌ **Content Needs Revision**\n\nIssues found:\n" + "\n".join([f"• {item}" for item in feedback])
            approval_status = "needs_revision"
        else:
            result_message = "✅ **Content Approved**\n\nAll rules have been met!"
            approval_status = "approved"
        
        # Send the review result back to this task
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=result_message,
            ),
        )
        
        # Also send the result back to the orchestrator agent if this request came from another agent
        if params.event.content.author == "agent" and orchestrator_task_id:
            try:
                # Send result back to orchestrator using Pydantic model
                result_data = CriticResponse(
                    feedback=feedback,
                    approval_status=approval_status,
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
                logger.info(f"Sent review result back to orchestrator for task {orchestrator_task_id}")
                
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
        
        logger.info(f"Completed review for task {params.task.id}: {len(feedback)} issues found")
        
    except Exception as e:
        logger.error(f"Error in content review: {e}")
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=f"❌ Error reviewing content: {e}",
            ),
        )


@acp.on_task_cancel
async def handle_task_cancel(params: CancelTaskParams):
    """Handle task cancellation."""
    logger.info(f"Critic task cancelled: {params.task.id}")
