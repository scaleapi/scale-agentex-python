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
    assert_agent_response_contains,
)

AGENT_NAME = "s010-multiturn"


def test_multiturn_conversation():
    """Test multi-turn conversation with non-streaming messages."""
    with test_sync_agent(agent_name=AGENT_NAME) as test:
        messages = [
            "Hello, can you tell me a little bit about tennis? I want to you make sure you use the word 'tennis' in each response.",
            "Pick one of the things you just mentioned, and dive deeper into it.",
            "Can you now output a summary of this conversation",
        ]

        for msg in messages:
            response = test.send_message(msg)

            # Validate response
            assert_valid_agent_response(response)

            # Validate "tennis" appears in response (per agent's behavior)
            assert_agent_response_contains(response, "tennis")

        # Verify conversation history
        history = test.get_conversation_history()
        assert len(history) >= 6, f"Expected >= 6 messages (3 user + 3 agent), got {len(history)}"


def test_multiturn_streaming():
    """Test multi-turn conversation with streaming messages."""
    with test_sync_agent(agent_name=AGENT_NAME) as test:
        messages = [
            "Hello, can you tell me a little bit about tennis? I want you to make sure you use the word 'tennis' in each response.",
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

            # Validate "tennis" appears in response
            assert "tennis" in aggregated_content.lower(), f"Expected 'tennis' in: {aggregated_content[:100]}"

        # Verify conversation history
        history = test.get_conversation_history()
        assert len(history) >= 6, f"Expected >= 6 messages, got {len(history)}"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
