"""
Tests for s020-streaming (sync agent)

This test suite demonstrates testing a streaming sync agent using the AgentEx testing framework.

Test coverage:
- Multi-turn non-streaming conversation with state checking
- Multi-turn streaming conversation with state checking

Prerequisites:
    - AgentEx services running (make dev)
    - Agent running: agentex agents run --manifest manifest.yaml

Run tests:
    pytest tests/test_agent.py -v
"""

from agentex import Agentex
from agentex.lib.testing import (
    test_sync_agent,
    collect_streaming_deltas,
    assert_valid_agent_response,
)

AGENT_NAME = "s020-streaming"


def test_multiturn_conversation():
    """Test multi-turn conversation with non-streaming messages."""
    # Need direct client access to check state
    client = Agentex(api_key="test", base_url="http://localhost:5003")

    # Find agent ID
    agents = client.agents.list()
    agent = next((a for a in agents if a.name == AGENT_NAME), None)
    assert agent is not None, f"Agent {AGENT_NAME} not found"

    with test_sync_agent(agent_name=AGENT_NAME) as test:
        messages = [
            "Hello, can you tell me a little bit about tennis? I want to you make sure you use the word 'tennis' in each response.",
            "Pick one of the things you just mentioned, and dive deeper into it.",
            "Can you now output a summary of this conversation",
        ]

        for i, msg in enumerate(messages):
            response = test.send_message(msg)

            # Validate response
            assert_valid_agent_response(response)

            # Check state (requires direct client access)
            states = client.states.list(agent_id=agent.id, task_id=test.task_id)
            assert len(states) == 1

            state = states[0]
            assert state.state is not None
            assert state.state.get("system_prompt") == "You are a helpful assistant that can answer questions."

            # Check message history
            message_history = client.messages.list(task_id=test.task_id)
            assert len(message_history) == (i + 1) * 2, f"Expected {(i + 1) * 2} messages, got {len(message_history)}"


def test_multiturn_streaming():
    """Test multi-turn streaming conversation."""
    # Need direct client access to check state
    client = Agentex(api_key="test", base_url="http://localhost:5003")

    # Find agent ID
    agents = client.agents.list()
    agent = next((a for a in agents if a.name == AGENT_NAME), None)
    assert agent is not None, f"Agent {AGENT_NAME} not found"

    with test_sync_agent(agent_name=AGENT_NAME) as test:
        messages = [
            "Hello, can you tell me a little bit about tennis? I want you to make sure you use the word 'tennis' in each response.",
            "Pick one of the things you just mentioned, and dive deeper into it.",
            "Can you now output a summary of this conversation",
        ]

        for i, msg in enumerate(messages):
            # Get streaming response
            response_gen = test.send_message_streaming(msg)

            # Collect streaming deltas
            aggregated_content, chunks = collect_streaming_deltas(response_gen)

            # Validate streaming response
            assert aggregated_content is not None
            assert len(chunks) > 1, "Should receive multiple chunks in streaming response"

            # Check state
            states = client.states.list(agent_id=agent.id, task_id=test.task_id)
            assert len(states) == 1

            state = states[0]
            assert state.state is not None
            assert state.state.get("system_prompt") == "You are a helpful assistant that can answer questions."

            # Check message history
            message_history = client.messages.list(task_id=test.task_id)
            assert len(message_history) == (i + 1) * 2


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
