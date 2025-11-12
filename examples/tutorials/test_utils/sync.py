"""
Utility functions for testing AgentEx agents.

This module provides helper functions for validating agent responses
in both streaming and non-streaming scenarios.
"""
from __future__ import annotations

from typing import List, Callable, Optional, Generator

from agentex.types import TextDelta, TextContent
from agentex.types.agent_rpc_result import StreamTaskMessageDone
from agentex.types.agent_rpc_response import SendMessageResponse
from agentex.types.task_message_update import StreamTaskMessageFull, StreamTaskMessageDelta


def validate_text_content(content: TextContent, validator: Optional[Callable[[str], bool]] = None) -> str:
    """
    Validate that content is TextContent and optionally run a custom validator.

    Args:
        content: The content to validate
        validator: Optional function that takes the content string and returns True if valid

    Returns:
        The text content as a string

    Raises:
        AssertionError: If validation fails
    """
    assert isinstance(content, TextContent), f"Expected TextContent, got {type(content)}"
    assert isinstance(content.content, str), "Content should be a string"

    if validator:
        assert validator(content.content), f"Content validation failed: {content.content}"

    return content.content


def validate_text_in_string(text_to_find: str, text: str):
    """
    Validate that text is a string and optionally run a custom validator.

    Args:
        text: The text to validate
        validator: Optional function that takes the text string and returns True if valid
    """

    assert text_to_find in text, f"Expected to find '{text_to_find}' in text."


def collect_streaming_response(
    stream_generator: Generator[SendMessageResponse, None, None],
) -> tuple[str, List[SendMessageResponse]]:
    """
    Collect and validate a streaming response.

    Args:
        stream_generator: The generator yielding streaming chunks

    Returns:
        Tuple of (aggregated_content from deltas, full_content from full messages)

    Raises:
        AssertionError: If no chunks are received or no content is found
    """
    aggregated_content = ""
    chunks = []

    for chunk in stream_generator:
        task_message_update = chunk.result
        chunks.append(chunk)
        # Collect text deltas as they arrive
        if isinstance(task_message_update, StreamTaskMessageDelta) and task_message_update.delta is not None:
            delta = task_message_update.delta
            if isinstance(delta, TextDelta) and delta.text_delta is not None:
                aggregated_content += delta.text_delta

        # Or collect full messages
        elif isinstance(task_message_update, StreamTaskMessageFull):
            content = task_message_update.content
            if isinstance(content, TextContent):
                aggregated_content = content.content

        elif isinstance(task_message_update, StreamTaskMessageDone):
            # Handle non-streaming response case pattern
            break
    # Validate we received something
    if not chunks:
        raise AssertionError("No streaming chunks were received, when at least 1 was expected.")

    if not aggregated_content:
        raise AssertionError("No content was received in the streaming response.")

    return aggregated_content, chunks
