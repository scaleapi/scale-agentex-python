"""
Tests for ab010-multiturn (agentic agent)

This test suite demonstrates testing a multi-turn agentic agent using the AgentEx testing framework.

Test coverage:
- Multi-turn event sending with state management
- Streaming events

Prerequisites:
    - AgentEx services running (make dev)
    - Agent running: agentex agents run --manifest manifest.yaml

Run tests:
    pytest tests/test_agent.py -v
"""

import asyncio

import pytest

from agentex import AsyncAgentex
from agentex.lib.testing import (
    test_agentic_agent,
    assert_valid_agent_response,
)

AGENT_NAME = "ab010-multiturn"


@pytest.mark.asyncio
async def test_multiturn_with_state_management():
    """Test multi-turn conversation with state management validation."""
    # Need client access to check state
    client = AsyncAgentex(api_key="test", base_url="http://localhost:5003")

    # Get agent ID
    agents = await client.agents.list()
    agent = next((a for a in agents if a.name == AGENT_NAME), None)
    assert agent is not None, f"Agent {AGENT_NAME} not found"

    async with test_agentic_agent(agent_name=AGENT_NAME) as test:
        # Wait for state initialization
        await asyncio.sleep(1)

        # Check initial state
        states = await client.states.list(agent_id=agent.id, task_id=test.task_id)
        assert len(states) == 1

        state = states[0].state
        assert state is not None
        messages = state.get("messages", [])
        assert isinstance(messages, list)
        assert len(messages) == 1  # Initial system message
        assert messages[0] == {
            "role": "system",
            "content": "You are a helpful assistant that can answer questions.",
        }

        # Send first message
        user_message = "Hello! Here is my test message"
        response = await test.send_event(user_message, timeout_seconds=30.0)
        assert_valid_agent_response(response)

        # Wait for state update (agent may or may not update state with messages)
        await asyncio.sleep(2)

        # Check if state was updated (optional - depends on agent implementation)
        states = await client.states.list(agent_id=agent.id, task_id=test.task_id)
        if len(states) > 0:
            state = states[0].state
            messages = state.get("messages", [])
            assert isinstance(messages, list)
            # Note: State updates depend on agent implementation
            print(f"State has {len(messages)} messages")


@pytest.mark.asyncio
async def test_streaming_events():
    """Test streaming events from agentic agent."""
    async with test_agentic_agent(agent_name=AGENT_NAME) as test:
        user_message = "Hello! Stream this response"

        events_received = []

        # Stream events
        async for event in test.send_event_and_stream(user_message, timeout_seconds=30.0):
            events_received.append(event)
            event_type = event.get("type")

            if event_type == "done":
                break

        # Validate we received events
        assert len(events_received) > 0, "Should receive streaming events"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
