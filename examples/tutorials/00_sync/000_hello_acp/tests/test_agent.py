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

import pytest 

from agentex.lib.testing import (
    test_sync_agent,
    collect_streaming_deltas,
    assert_valid_agent_response,
)

AGENT_NAME = "s000-hello-acp"


@pytest.fixture
def agent_name():
    """Return the agent name for testing."""
    return AGENT_NAME

@pytest.fixture
def test_agent(agent_name: str):
    """Fixture to create a test sync agent."""
    with test_sync_agent(agent_name=agent_name) as test:
        yield test


class TestNonStreamingMessages:
    """Test non-streaming message sending."""

    def test_send_simple_message(self, test_agent):
        """Test sending a simple message and receiving a response."""
        message_content = "Hello, Agent! How are you?"
        response = test_agent.send_message(message_content)

        # Validate response
        assert_valid_agent_response(response)

        # Check expected response format
        expected = f"Hello! I've received your message. Here's a generic response, but in future tutorials we'll see how you can get me to intelligently respond to your message. This is what I heard you say: {message_content}"
        assert response.content == expected, f"Expected: {expected}\nGot: {response.content}"

class TestStreamingMessages:
    """Test streaming message sending."""

    def test_stream_simple_message(self, test_agent):
        """Test streaming a simple message and aggregating deltas."""
        message_content = "Hello, Agent! Can you stream your response?"

        # Get streaming response
        response_gen = test_agent.send_message_streaming(message_content)

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
