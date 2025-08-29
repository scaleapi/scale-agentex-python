"""
ACPAgentBridge - Platform-agnostic conversion between ACP events and agent formats.

This bridge handles conversion between Agentex's ACP protocol and various agent platform formats,
maintaining compatibility across OpenAI Agents SDK, LangChain, CrewAI, and other frameworks.
"""

from typing import Any
from agentex.lib.types.acp import Event
from agentex.types.text_content import TextContent
from agentex.types.data_content import DataContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.task_message_content import TaskMessageContent
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

class ACPAgentBridge:
    """Platform-agnostic conversion utilities for ACP ↔ Agent communication"""
    
    @staticmethod
    def acp_event_to_agent_input(event: Event) -> str:
        """
        Convert ACP Event to platform-agnostic agent input string.
        
        Args:
            event: ACP Event containing TaskMessageContent
            
        Returns:
            str: Platform-agnostic input suitable for any agent framework
        """
        if not event.content:
            logger.warning(f"Event {event.id} has no content, returning empty string")
            return ""
        
        content = event.content
        
        # Handle different TaskMessageContent types
        if hasattr(content, 'type'):
            if content.type == "text":
                return content.content if hasattr(content, 'content') else ""
            elif content.type == "data":
                # Convert data dict to string representation
                if hasattr(content, 'data') and content.data:
                    return str(content.data)
                return ""
            elif content.type == "reasoning":
                # Extract reasoning summary and content
                if hasattr(content, 'summary') and content.summary:
                    summary_text = " ".join(content.summary)
                    if hasattr(content, 'content') and content.content:
                        reasoning_text = " ".join(content.content)
                        return f"{summary_text}\n{reasoning_text}"
                    return summary_text
                return ""
            elif content.type in ["tool_request", "tool_response"]:
                # For tool-related content, extract relevant information
                # This would need expansion based on actual tool content structure
                return str(content) if content else ""
        
        # Fallback: convert to string
        logger.warning(f"Unknown content type for event {event.id}, using string conversion")
        return str(content)
    
    @staticmethod
    async def agent_output_to_acp_message(output: str, task_id: str, author: str = "agent") -> None:
        """
        Send agent output as ACP message using Agentex ADK.
        
        Args:
            output: Agent's output text
            task_id: Task ID to send message to
            author: Message author (default: "agent")
        """
        try:
            # Import here to avoid circular imports
            from agentex.lib import adk
            
            # Create TextContent message
            text_content = TextContent(
                author=author,
                content=output,
                type="text"
            )
            
            # Send via ADK messages
            await adk.messages.create(
                task_id=task_id,
                content=text_content
            )
            
            logger.debug(f"Sent agent output to task {task_id}: {output[:100]}...")
            
        except Exception as e:
            logger.error(f"Failed to send agent output to ACP: {e}")
            raise
    
    @staticmethod
    def extract_user_input_from_event(event: Event) -> tuple[str, str]:
        """
        Extract user input and author from ACP event.
        
        Returns:
            tuple[str, str]: (input_text, author)
        """
        input_text = ACPAgentBridge.acp_event_to_agent_input(event)
        
        # Extract author if available
        author = "user"  # default
        if event.content and hasattr(event.content, 'author'):
            author = event.content.author
        
        return input_text, author
