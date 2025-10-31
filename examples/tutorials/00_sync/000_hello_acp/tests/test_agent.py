"""
Tests for s000-hello-acp (sync agent)

This test suite demonstrates testing a sync agent using the AgentEx testing framework.

Test coverage:
- Non-streaming message sending
- Streaming message sending

Prerequisites:
    - AgentEx services running (make dev)
    - Agent running: agentex agents run --manifest manifest.yaml

Run tests:
    pytest tests/test_agent.py -v
"""

from agentex.lib.testing import (
    test_sync_agent,
    collect_streaming_deltas,
    assert_valid_agent_response,
)

AGENT_NAME = "s000-hello-acp"


def test_send_simple_message():
    """Test sending a simple message and receiving a response."""
    with test_sync_agent(agent_name=AGENT_NAME) as test:
        message_content = "Hello, Agent! How are you?"
        response = test.send_message(message_content)

        # Validate response
        assert_valid_agent_response(response)

        # Check expected response format
        expected = f"Hello! I've received your message. Here's a generic response, but in future tutorials we'll see how you can get me to intelligently respond to your message. This is what I heard you say: {message_content}"
        assert response.content == expected, f"Expected: {expected}\nGot: {response.content}"


def test_stream_simple_message():
    """Test streaming a simple message and aggregating deltas."""
    with test_sync_agent(agent_name=AGENT_NAME) as test:
        message_content = "Hello, Agent! Can you stream your response?"

        # Get streaming response
        response_gen = test.send_message_streaming(message_content)

        # Collect streaming deltas
        aggregated_content, chunks = collect_streaming_deltas(response_gen)

        # Validate we got content
        assert len(chunks) > 0, "Should receive at least one chunk"
        assert len(aggregated_content) > 0, "Should receive content"

        # Check expected response format
        expected = f"Hello! I've received your message. Here's a generic response, but in future tutorials we'll see how you can get me to intelligently respond to your message. This is what I heard you say: {message_content}"
        assert aggregated_content == expected, f"Expected: {expected}\nGot: {aggregated_content}"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
