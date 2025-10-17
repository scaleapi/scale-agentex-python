"""
Testing Assertions

Assertion helpers for validating agent responses and behavior.
"""
from __future__ import annotations

from agentex.types.text_content import TextContent


def assert_agent_response_contains(response: TextContent, expected_text: str):
    """
    Assert agent response contains expected text (case-insensitive).

    Args:
        response: Agent's response
        expected_text: Text that should be present

    Example:
        response = test.send_message("What's 2+2?")
        assert_agent_response_contains(response, "4")
    """
    if not isinstance(response, TextContent):
        raise AssertionError(f"Expected TextContent, got {type(response)}")

    assert expected_text.lower() in response.content.lower(), (
        f"Expected '{expected_text}' in response: {response.content}"
    )


def assert_valid_agent_response(response: TextContent):
    """
    Assert response is valid and from agent.

    Args:
        response: Agent's response to validate

    Example:
        response = test.send_message("Hello")
        assert_valid_agent_response(response)
    """
    assert response is not None, "Agent response should not be None"
    assert isinstance(response, TextContent), f"Expected TextContent, got {type(response)}"
    assert response.author == "agent", f"Response should be from agent, got {response.author}"
    assert len(response.content.strip()) > 0, "Agent response should have content"


def assert_conversation_maintains_context(conversation_history: list[TextContent], context_keywords: list[str]):
    """
    Assert conversation maintains context across turns.

    Args:
        conversation_history: Full conversation history
        context_keywords: Keywords that should appear in later messages

    Example:
        test.send_message("My name is Alice")
        test.send_message("What's my name?")
        history = test.get_conversation_history()
        assert_conversation_maintains_context(history, ["Alice"])
    """
    if len(conversation_history) < 2:
        return

    text_messages = [msg.content for msg in conversation_history if isinstance(msg, TextContent)]

    for keyword in context_keywords:
        found = any(keyword.lower() in msg.lower() for msg in text_messages[2:])
        assert found, f"Context keyword '{keyword}' not maintained in conversation"


def extract_response_text(response: TextContent) -> str:
    """
    Extract text content from agent response.

    Args:
        response: Agent response

    Returns:
        Text content as string

    Example:
        text = extract_response_text(response)
        assert len(text) > 0
    """
    if response is None:
        return ""

    if isinstance(response, TextContent):
        return response.content

    return str(response)
