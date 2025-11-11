"""
Tests for s010-multiturn (sync agent)

This test suite demonstrates testing a multi-turn sync agent using the AgentEx testing framework.

Test coverage:
- Multi-turn non-streaming conversation
- Multi-turn streaming conversation
- State management across turns

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

AGENT_NAME = "s010-multiturn"

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
        messages = [
            "Hello, can you tell me a litle bit about tennis? I want to you make sure you use the word 'tennis' in each response.",
            "Pick one of the things you just mentioned, and dive deeper into it.",
            "Can you now output a summary of this conversation",
        ]
        for i, msg in enumerate(messages):
            response = test_agent.send_message(msg)

            # Validate response (agent may require OpenAI key)
            assert_valid_agent_response(response)

            # Validate that "tennis" appears in the response because that is what our model does
            assert "tennis" in response.content.lower()

            # Verify conversation history
            message_history = test_agent.get_conversation_history()
            assert len(message_history) == (i + 1) * 2  # user + agent messages



def test_multiturn_conversation():
    """Test multi-turn conversation with non-streaming messages."""
    with test_sync_agent(agent_name=AGENT_NAME) as test:





def test_multiturn_streaming():
    """Test multi-turn conversation with streaming messages."""
    with test_sync_agent(agent_name=AGENT_NAME) as test:
        messages = [
            "Hello, can you tell me a litle bit about tennis? I want to you make sure you use the word 'tennis' in each response.",
            "Pick one of the things you just mentioned, and dive deeper into it.",
            "Can you now output a summary of this conversation",
        ]

        for msg in messages:
            # Get streaming response
            response_gen = test.send_message_streaming(msg)

            # Collect streaming deltas
            aggregated_content, chunks = collect_streaming_deltas(response_gen)

            # Validate we got content
            assert len(chunks) > 0, "Should receive chunks"
            assert len(aggregated_content) > 0, "Should receive content"

            # Validate that "tennis" appears in the response because that is what our model does
            assert "tennis" in aggregated_content.lower()

        # Verify conversation history (only user messages tracked with streaming)
        history = test.get_conversation_history()
        assert len(history) >= 3, f"Expected >= 3 user messages, got {len(history)}"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
