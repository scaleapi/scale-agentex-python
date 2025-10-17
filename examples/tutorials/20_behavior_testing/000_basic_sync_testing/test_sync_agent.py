"""
Tutorial 20.0: Basic Sync Agent Testing

This tutorial demonstrates how to test sync agents using the agentex.lib.testing framework.

Prerequisites:
    - AgentEx services running (make dev)
    - A sync agent running (e.g., tutorial 00_sync/000_hello_acp)

Run:
    pytest test_sync_agent.py -v
"""

from agentex.lib.testing import (
    assert_agent_response_contains,
    assert_conversation_maintains_context,
    assert_valid_agent_response,
    test_sync_agent,
)


def test_sync_agent_responds():
    """Test that sync agent responds to a simple message."""
    with test_sync_agent() as test:
        # Send a message
        response = test.send_message("Hello! How are you?")

        # Verify we got a valid response
        assert_valid_agent_response(response)
        print(f"✓ Agent responded: {response.content[:50]}...")


def test_sync_agent_multi_turn():
    """Test that sync agent handles multi-turn conversation."""
    with test_sync_agent() as test:
        # First exchange
        response1 = test.send_message("Hello!")
        assert_valid_agent_response(response1)

        # Second exchange
        response2 = test.send_message("Can you help me with something?")
        assert_valid_agent_response(response2)

        # Third exchange
        response3 = test.send_message("Thank you!")
        assert_valid_agent_response(response3)

        # Verify conversation history
        history = test.get_conversation_history()
        assert len(history) >= 6  # 3 user + 3 agent messages
        print(f"✓ Completed {len(history)} message conversation")


def test_sync_agent_context():
    """Test that sync agent maintains conversation context."""
    with test_sync_agent() as test:
        # Establish context
        response1 = test.send_message("My name is Sarah and I'm a teacher")
        assert_valid_agent_response(response1)

        # Query the context
        response2 = test.send_message("What is my name?")
        assert_valid_agent_response(response2)

        # Check context is maintained (agent should mention Sarah)
        history = test.get_conversation_history()
        assert_conversation_maintains_context(history, ["Sarah"])
        print("✓ Agent maintained conversation context")


def test_sync_agent_specific_content():
    """Test that agent responds with expected content."""
    with test_sync_agent() as test:
        # Ask a factual question
        response = test.send_message("What is 2 plus 2?")

        # Verify response is valid
        assert_valid_agent_response(response)

        # Verify response contains expected content
        # (This assumes the agent can do basic math)
        assert_agent_response_contains(response, "4")
        print(f"✓ Agent provided correct answer: {response.content[:50]}...")


def test_sync_agent_conversation_length():
    """Test conversation history tracking."""
    with test_sync_agent() as test:
        # Send 3 messages
        test.send_message("First message")
        test.send_message("Second message")
        test.send_message("Third message")

        # Get history
        history = test.get_conversation_history()

        # Should have 6 messages: 3 user + 3 agent
        assert len(history) >= 6, f"Expected >= 6 messages, got {len(history)}"
        print(f"✓ Conversation history contains {len(history)} messages")


if __name__ == "__main__":
    print("Run with: pytest test_sync_agent.py -v")
