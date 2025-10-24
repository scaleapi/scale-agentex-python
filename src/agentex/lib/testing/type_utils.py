"""
Type conversion utilities for AgentEx testing framework.

Handles conversion between request types (*Param) and response types.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentex.types import SendMessageResponse, SendEventResponse
    from agentex.types.text_content import TextContent

from agentex.types.text_content_param import TextContentParam
from agentex.lib.testing.exceptions import AgentResponseError

logger = logging.getLogger(__name__)


def create_user_message(content: str) -> TextContentParam:
    """
    Create a user message parameter for sending to agent.

    Args:
        content: Message text

    Returns:
        TextContentParam ready to send to agent
    """
    return TextContentParam(type="text", author="user", content=content)


def extract_agent_response(response: SendMessageResponse | SendEventResponse, agent_id: str) -> TextContent:
    """
    Extract agent response from RPC response.

    The SDK returns RPC-style responses. This extracts the actual TextContent.

    Args:
        response: Response from send_message or send_event
        agent_id: Agent ID for error messages

    Returns:
        TextContent response from agent

    Raises:
        AgentResponseError: If response structure is invalid
    """
    from agentex.types.text_content import TextContent

    # Try to extract from RPC result structure
    if hasattr(response, "result") and response.result is not None:
        result = response.result

        # SendMessageResponse: result.content
        if hasattr(result, "content"):
            content = result.content
            if isinstance(content, TextContent):
                return content

        # SendEventResponse: result.message.content
        if hasattr(result, "message") and result.message:
            if hasattr(result.message, "content"):
                content = result.message.content
                if isinstance(content, TextContent):
                    return content

    # Try direct content access (fallback)
    if hasattr(response, "content"):
        content = response.content
        if isinstance(content, TextContent):
            return content

    # No valid response found
    logger.error(f"Could not extract content from response: {type(response).__name__}")
    logger.debug(f"Response: {response}")

    raise AgentResponseError(agent_id, f"Could not extract TextContent from response type: {type(response).__name__}")


def extract_task_id_from_response(response: SendEventResponse) -> str | None:
    """
    Extract task ID from send_event response.

    When send_event auto-creates a task, the task ID is in the response.

    Args:
        response: Response from send_event

    Returns:
        Task ID if found, None otherwise
    """
    # Try to extract task_id from result
    if hasattr(response, "result") and response.result:
        result = response.result

        # Direct task_id field
        if hasattr(result, "task_id") and result.task_id:
            return result.task_id

        # task_id in message
        if hasattr(result, "message") and result.message:
            if hasattr(result.message, "task_id") and result.message.task_id:
                return result.message.task_id

    logger.debug("Could not extract task_id from send_event response")
    return None
