"""
Tests for ab020-streaming (agentic agent)

Test coverage:
- Event sending and polling
- Streaming responses

Prerequisites:
    - AgentEx services running (make dev)
    - Agent running: agentex agents run --manifest manifest.yaml

Run: pytest tests/test_agent.py -v
"""
import asyncio

import pytest

from agentex import AsyncAgentex
from agentex.lib.testing import (
    assert_valid_agent_response,
    test_agentic_agent,
)

AGENT_NAME = "ab020-streaming"


@pytest.mark.asyncio
async def test_send_event_and_poll():
    """Test sending events and polling for responses."""
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

        # Check if state was updated
        states = await client.states.list(agent_id=agent.id, task_id=test.task_id)
        state = states[0].state
        messages = state.get("messages", [])
        assert isinstance(messages, list)
        assert len(messages) == 3


@pytest.mark.asyncio
async def test_streaming_events():
    """Test streaming event responses."""
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

        # Send message and stream response
        user_message = "Hello! Stream this response"

        events_received = []
        agent_response_found = False
        delta_messages_found = False

        # Stream events
        async for event in test.send_event_and_stream(user_message, timeout_seconds=30.0):
            events_received.append(event)
            event_type = event.get("type")

            if event_type == "done":
                break
            elif event_type == "full":
                content = event.get("content", {})
                if content.get("author") == "agent":
                    agent_response_found = True
            elif event_type == "delta":
                delta_messages_found = True

        # Validate we received events
        assert len(events_received) > 0, "Should receive streaming events"
        assert agent_response_found, "Should receive agent response event"
        assert delta_messages_found, "Should receive delta agent message events"

        # Verify state has been updated
        await asyncio.sleep(1) # Wait for state update
        
        states = await client.states.list(agent_id=agent.id, task_id=test.task_id)
        assert len(states) == 1
        state = states[0].state
        messages = state.get("messages", [])

        assert isinstance(messages, list)
        assert len(messages) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
