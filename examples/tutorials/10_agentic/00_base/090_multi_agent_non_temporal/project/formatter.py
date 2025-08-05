# Formatter Agent - Converts approved content to various target formats

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

from models import FormatterRequest, FormatterResponse
from agentex.lib.utils.model_utils import BaseModel

logger = make_logger(__name__)

# Create an ACP server with base configuration
acp = FastACP.create(
    acp_type="agentic",
    config=AgenticACPConfig(
        type="base",
    ),
)


class FormatterState(BaseModel):
    messages: List[Message]
    format_history: List[dict] = []


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    """Initialize the formatter agent state."""
    logger.info(f"Formatter task created: {params.task.id}")
    
    # Initialize state with system message
    system_message = SystemMessage(
        content="""You are a professional content formatter specialist. Your job is to convert approved content into various target formats while preserving the original message and quality.

Your responsibilities:
1. Convert content to the specified target format (HTML, Markdown, JSON, etc.)
2. Apply proper formatting conventions for the target format
3. Preserve all content and meaning during conversion
4. Ensure the formatted output is valid and well-structured

Supported formats:
- HTML: Convert to clean, semantic HTML with appropriate tags
- Markdown: Convert to properly formatted Markdown syntax
- JSON: Structure content in a meaningful JSON format
- Text: Clean plain text formatting
- Email: Format as professional email with proper structure

When formatting:
1. Maintain the original content's meaning and tone
2. Apply format-specific best practices
3. Ensure proper structure and readability
4. Use semantic elements appropriate to the format

You must respond with a JSON object in this exact format:
{
  "formatted_content": "the fully formatted content here"
}

Do not include any other text, explanations, or formatting outside the JSON response."""
    )
    
    state = FormatterState(messages=[system_message])
    await adk.state.create(task_id=params.task.id, agent_id=params.agent.id, state=state)
    
    await adk.messages.create(
        task_id=params.task.id,
        content=TextContent(
            author="agent",
            content="🎨 **Formatter Agent** - Content Format Conversion\n\nI specialize in converting approved content to various target formats while preserving meaning and quality.\n\nSend me a JSON request with:\n```json\n{\n  \"content\": \"Content to format\",\n  \"target_format\": \"HTML|Markdown|JSON|Text|Email\"\n}\n```\n\nI'll respond with formatted content JSON:\n```json\n{\n  \"formatted_content\": \"Your beautifully formatted content\"\n}\n```\n\nSupported formats: HTML, Markdown, JSON, Text, Email\nReady to make your content shine! ✨",
        ),
    )


@acp.on_task_event_send
async def handle_event_send(params: SendEventParams):
    """Handle content formatting requests."""
    
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
                    content="❌ Please provide a valid JSON request with 'content' and 'target_format' fields.",
                ),
            )
            return
        
        # Validate required fields
        if "content" not in request_data or "target_format" not in request_data:
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content="❌ Missing required fields: 'content' and 'target_format'",
                ),
            )
            return
        
        # Parse and validate request using Pydantic
        try:
            formatter_request = FormatterRequest.model_validate(request_data)
        except ValueError as e:
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content=f"❌ Invalid request format: {e}",
                ),
            )
            return
        
        content_to_format = formatter_request.content
        target_format = formatter_request.target_format.upper()
        orchestrator_task_id = formatter_request.orchestrator_task_id
        
        # Validate target format
        supported_formats = ["HTML", "MARKDOWN", "JSON", "TEXT", "EMAIL"]
        if target_format not in supported_formats:
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content=f"❌ Unsupported format: {target_format}. Supported formats: {', '.join(supported_formats)}",
                ),
            )
            return
        
        # Get current state
        task_state = await adk.state.get_by_task_and_agent(task_id=params.task.id, agent_id=params.agent.id)
        state = FormatterState.model_validate(task_state.state)
        
        # Add this format request to history
        state.format_history.append({
            "content": content_to_format,
            "target_format": target_format,
            "timestamp": "now"  # In real implementation, use proper timestamp
        })
        
        # Send status update
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=f"🎨 **Formatting Content** (Request #{len(state.format_history)})\n\nConverting to {target_format} format...",
            ),
        )
        
        # Create formatting prompt based on target format
        format_instructions = {
            "HTML": "Convert to clean, semantic HTML with appropriate tags (headings, paragraphs, lists, etc.). Use proper HTML structure.",
            "MARKDOWN": "Convert to properly formatted Markdown syntax with appropriate headers, emphasis, lists, and other Markdown elements.",
            "JSON": "Structure the content in a meaningful JSON format with appropriate keys and values that represent the content structure.",
            "TEXT": "Format as clean, well-structured plain text with proper line breaks and spacing.",
            "EMAIL": "Format as a professional email with proper subject, greeting, body, and closing."
        }
        
        user_message_content = f"""Please format the following content into {target_format} format:

CONTENT TO FORMAT:
{content_to_format}

FORMATTING INSTRUCTIONS:
{format_instructions[target_format]}

Requirements:
1. Preserve all original meaning and content
2. Apply best practices for {target_format} formatting
3. Ensure the output is valid and well-structured
4. Maintain readability and professional appearance

You MUST respond with a JSON object in this exact format:
{{
  "formatted_content": "the fully formatted content here"
}}

Do not include any other text, explanations, or formatting outside the JSON response."""
        
        # Add user message to conversation
        state.messages.append(UserMessage(content=user_message_content))
        
        # Generate formatted content using LLM
        chat_completion = await adk.providers.litellm.chat_completion(
            llm_config=LLMConfig(model="gpt-4o-mini", messages=state.messages),
            trace_id=params.task.id,
        )
        
        if not chat_completion.choices or not chat_completion.choices[0].message:
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content="❌ Failed to format content. Please try again.",
                ),
            )
            return
        
        format_response = chat_completion.choices[0].message.content or ""
        
        # Add assistant response to conversation
        state.messages.append(AssistantMessage(content=format_response))
        
        # Parse the format response
        try:
            format_data = json.loads(format_response.strip())
            formatted_content = format_data.get("formatted_content", "")
        except json.JSONDecodeError:
            # Fallback if LLM doesn't return valid JSON
            formatted_content = format_response.strip()
        
        # Create result message
        result_message = f"✅ **Content Formatted Successfully**\n\nFormat: {target_format}\n\n**Formatted Content:**\n```{target_format.lower()}\n{formatted_content}\n```"
        
        # Send the formatted content back to this task
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
                # Send result back to orchestrator
                # Send result back to orchestrator using Pydantic model
                result_data = FormatterResponse(
                    formatted_content=formatted_content,
                    target_format=target_format,
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
                logger.info(f"Sent formatted content back to orchestrator for task {orchestrator_task_id}")
                
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
        
        logger.info(f"Completed formatting for task {params.task.id}: {target_format}")
        
    except Exception as e:
        logger.error(f"Error in content formatting: {e}")
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=f"❌ Error formatting content: {e}",
            ),
        )


@acp.on_task_cancel
async def handle_task_cancel(params: CancelTaskParams):
    """Handle task cancellation."""
    logger.info(f"Formatter task cancelled: {params.task.id}")
