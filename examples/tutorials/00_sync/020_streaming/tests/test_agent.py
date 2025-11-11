"""
Tests for s020-streaming (sync agent with state management)

This test suite validates:
- Non-streaming message sending with state tracking
- Streaming message sending with state tracking
- Message history validation
- State persistence across turns

Prerequisites:
    - AgentEx services running (make dev)
    - Agent running: agentex agents run --manifest manifest.yaml

Run: pytest tests/test_agent.py -v
"""

import pytest

from agentex import Agentex
from agentex.lib.testing import (
    test_sync_agent,
    collect_streaming_deltas,
    assert_valid_agent_response,
)

AGENT_NAME = "s020-streaming"


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

    def test_send_message(self, test_agent):
        messages = [
            "Hello, can you tell me a little bit about tennis? I want to you make sure you use the word 'tennis' in each response.",
            "Pick one of the things you just mentioned, and dive deeper into it.",
            "Can you now output a summary of this conversation",
        ]

        for i, msg in enumerate(messages):
            response = test_agent.send_message(msg)

            # Validate response (agent may require OpenAI key)
            assert_valid_agent_response(response)

            # Validate that "tennis" appears in the response because that is what our model does
            assert "tennis" in response.content.lower()

            states = test_agent.client.states.list(task_id=test_agent.task_id)
            assert len(states) == 1

            state = states[0]
            assert state.state is not None
            assert state.state.get("system_prompt") == "You are a helpful assistant that can answer questions."

            # Verify conversation history
            message_history = test_agent.client.messages.list(task_id=test_agent.task_id)
            assert len(message_history) == (i + 1) * 2  # user + agent messages


class TestStreamingMessages:
    """Test streaming message sending."""

    def test_send_stream_message(self, test_agent):
        """Test streaming messages in a multi-turn conversation."""
        messages = [
            "Hello, can you tell me a little bit about tennis? I want you to make sure you use the word 'tennis' in each response.",
            "Pick one of the things you just mentioned, and dive deeper into it.",
            "Can you now output a summary of this conversation",
        ]

        for i, msg in enumerate(messages):
            # Get streaming response
            response_gen = test_agent.send_message_streaming(msg)

            # Collect the streaming response
            aggregated_content, chunks = collect_streaming_deltas(response_gen)

            assert len(chunks) > 1

            # Validate we got content
            assert len(aggregated_content) > 0, "Should receive content"

            # Validate that "tennis" appears in the response because that is what our model does
            assert "tennis" in aggregated_content.lower()

            states = test_agent.client.states.list(task_id=test_agent.task_id)
            assert len(states) == 1

            message_history = test_agent.client.messages.list(task_id=test_agent.task_id)
            assert len(message_history) == (i + 1) * 2 # user + agent messages


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
