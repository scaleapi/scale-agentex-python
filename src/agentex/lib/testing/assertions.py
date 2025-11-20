"""
Testing Assertions

Assertion helpers for validating agent responses and behavior.
"""

from __future__ import annotations

from agentex.types.text_content import TextContent


def assert_agent_response_contains(response: TextContent, expected_text: str, case_sensitive: bool = False):
    """
    Assert agent response contains expected text.

    Args:
        response: Agent's response
        expected_text: Text that should be present
        case_sensitive: Whether to perform case-sensitive comparison (default: False)

    Raises:
        AssertionError: If expected text not found in response

    Example:
        response = test.send_message("What's 2+2?")
        assert_agent_response_contains(response, "4")
    """
    if not isinstance(response, TextContent):
        raise AssertionError(
            f"Expected TextContent response, got {type(response).__name__}. "
            f"Check that agent is returning proper response format."
        )

    actual_content = response.content if case_sensitive else response.content.lower()
    expected = expected_text if case_sensitive else expected_text.lower()

    if expected not in actual_content:
        # Show snippet of actual content for context
        snippet = response.content[:100] + "..." if len(response.content) > 100 else response.content
        raise AssertionError(
            f"Expected text not found in response.\n"
            f"  Expected: '{expected_text}'\n"
            f"  Actual response: '{snippet}'\n"
            f"  Case sensitive: {case_sensitive}"
        )


def assert_valid_agent_response(response: TextContent):
    """
    Assert response is valid and from agent.

    Validates:
    - Response is not None
    - Response is TextContent
    - Response author is 'agent'
    - Response has non-empty content

    Args:
        response: Agent's response to validate

    Raises:
        AssertionError: If any validation fails

    Example:
        response = test.send_message("Hello")
        assert_valid_agent_response(response)
    """
    if response is None:
        raise AssertionError("Agent response is None. Check if agent is responding correctly.")

    if not isinstance(response, TextContent):
        raise AssertionError(
            f"Expected TextContent, got {type(response).__name__}. Agent may be returning incorrect response format."
        )

    if response.author != "agent":
        raise AssertionError(
            f"Response author should be 'agent', got '{response.author}'. Check message routing and author assignment."
        )

    if not response.content or len(response.content.strip()) == 0:
        raise AssertionError("Agent response content is empty. Agent may be failing to generate response.")


def assert_conversation_maintains_context(conversation_history: list[str], context_keywords: list[str]):
    """
    Assert conversation maintains context across turns.

    Checks that keywords introduced early in the conversation appear
    in later messages, indicating context retention.

    Args:
        conversation_history: Full conversation history as list of strings
        context_keywords: Keywords that should appear in later messages

    Raises:
        AssertionError: If context is not maintained

    Example:
        test.send_message("My name is Alice")
        test.send_message("What's my name?")
        history = test.get_conversation_history()
        assert_conversation_maintains_context(history, ["Alice"])
    """
    if len(conversation_history) < 2:
        return  # Not enough messages to check context

    # History is now just strings
    if len(conversation_history) < 2:
        return  # Not enough text messages

    # Check messages after the first 2 (skip initial context establishment)
    later_messages = conversation_history[2:] if len(conversation_history) > 2 else conversation_history

    missing_keywords = []
    for keyword in context_keywords:
        found = any(keyword.lower() in msg.lower() for msg in later_messages)
        if not found:
            missing_keywords.append(keyword)

    if missing_keywords:
        raise AssertionError(
            f"Context keywords not maintained in conversation: {missing_keywords}\n"
            f"  Total messages: {len(conversation_history)}\n"
            f"  Expected keywords: {context_keywords}\n"
            f"  Missing: {missing_keywords}\n"
            "Agent may not be maintaining conversation context properly."
        )
