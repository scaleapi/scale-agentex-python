"""
Tests for ab010-multiturn (async agent)

This test suite demonstrates testing a multi-turn async agent using the AgentEx testing framework.

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
import pytest_asyncio

from agentex.lib.testing import (
    async_test_agent,
    stream_agent_response,
    assert_valid_agent_response,
)
from agentex.lib.testing.sessions import AsyncAgentTest

AGENT_NAME = "ab010-multiturn"


@pytest.fixture
def agent_name():
    """Return the agent name for testing."""
    return AGENT_NAME


@pytest_asyncio.fixture
async def test_agent(agent_name: str):
    """Fixture to create a test async agent."""
    async with async_test_agent(agent_name=agent_name) as test:
        yield test


class TestNonStreamingEvents:
    """Test non-streaming event sending and polling."""

    @pytest.mark.asyncio
    async def test_send_event_and_poll(self, test_agent: AsyncAgentTest):
        """Test sending an event and polling for the response."""
        await asyncio.sleep(1)  # Wait for state initialization
        states = await test_agent.client.states.list(agent_id=test_agent.agent.id, task_id=test_agent.task_id)
        assert len(states) == 1
        # Check initial state
        state = states[0].state
        assert state is not None
        messages = state.get("messages", [])
        assert isinstance(messages, list)
        assert len(messages) == 1  # Initial system message
        assert messages[0] == {
            "role": "system",
            "content": "You are a helpful assistant that can answer questions.",
        }

        user_message = "Hello! Here is my test message"
        response = await test_agent.send_event(user_message, timeout_seconds=30.0)
        assert_valid_agent_response(response)

        # Wait for state update
        await asyncio.sleep(2)

        # Check if state was updated (optional - depends on agent implementation)
        states = await test_agent.client.states.list(agent_id=test_agent.agent.id, task_id=test_agent.task_id)
        assert len(states) == 1
        state = states[0].state
        messages = state.get("messages", [])
        assert isinstance(messages, list)
        assert len(messages) == 3


class TestStreamingEvents:
    """Test streaming event sending."""

    @pytest.mark.asyncio
    async def test_streaming_events(self, test_agent: AsyncAgentTest):
        """Test streaming events from async agent."""
        # Wait for state initialization
        await asyncio.sleep(1)

        # Check initial state
        states = await test_agent.client.states.list(agent_id=test_agent.agent.id, task_id=test_agent.task_id)
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
        user_echo_found = False
        agent_response_found = False

        # Stream events
        async for event in stream_agent_response(test_agent.client, test_agent.task_id, timeout=30.0):
            events_received.append(event)
            event_type = event.get("type")

            if event_type == "connected":
                await test_agent.send_event(user_message, timeout_seconds=30.0)

            elif event_type == "done":
                break

            elif event_type == "full":
                content = event.get("content", {})
                if content.get("content") is None:
                    continue  # Skip empty content

                if content.get("type") == "text" and content.get("author") == "agent":
                    # Check for agent response to user message
                    agent_response_found = True
                    assert user_echo_found, "User echo should be found before agent response"

                elif content.get("type") == "text" and content.get("author") == "user":
                    # Check for user message echo
                    if content.get("content") == user_message:
                        user_echo_found = True

                if agent_response_found and user_echo_found:
                    break

        # Validate we received events
        assert len(events_received) > 0, "Should receive streaming events"
        assert agent_response_found, "Should receive agent response event"
        assert user_echo_found, "Should receive user message event"

        # Verify state has been updated
        await asyncio.sleep(1)  # Wait for state update

        states = await test_agent.client.states.list(agent_id=test_agent.agent.id, task_id=test_agent.task_id)
        assert len(states) == 1
        state = states[0].state
        messages = state.get("messages", [])

        assert isinstance(messages, list)
        assert len(messages) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
