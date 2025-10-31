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

from agentex.lib.testing import (
    test_sync_agent,
    collect_streaming_deltas,
    assert_valid_agent_response,
)

AGENT_NAME = "s010-multiturn"


def test_multiturn_conversation():
    """Test multi-turn conversation with non-streaming messages."""
    with test_sync_agent(agent_name=AGENT_NAME) as test:
        messages = [
            "Hello",
            "How are you?",
            "Thank you",
        ]

        for msg in messages:
            response = test.send_message(msg)

            # Validate response (agent may require OpenAI key)
            assert_valid_agent_response(response)

        # Verify conversation history
        history = test.get_conversation_history()
        assert len(history) >= 6, f"Expected >= 6 messages (3 user + 3 agent), got {len(history)}"


def test_multiturn_streaming():
    """Test multi-turn conversation with streaming messages."""
    with test_sync_agent(agent_name=AGENT_NAME) as test:
        messages = [
            "Hello",
            "How are you?",
            "Thank you",
        ]

        for msg in messages:
            # Get streaming response
            response_gen = test.send_message_streaming(msg)

            # Collect streaming deltas
            aggregated_content, chunks = collect_streaming_deltas(response_gen)

            # Validate we got content
            assert len(chunks) > 0, "Should receive chunks"
            assert len(aggregated_content) > 0, "Should receive content"

        # Verify conversation history (only user messages tracked with streaming)
        history = test.get_conversation_history()
        assert len(history) >= 3, f"Expected >= 3 user messages, got {len(history)}"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
