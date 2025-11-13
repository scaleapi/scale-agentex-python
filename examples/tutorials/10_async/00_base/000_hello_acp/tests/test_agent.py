"""
Tests for ab000-hello-acp (async agent)

This test suite demonstrates testing an async agent using the AgentEx testing framework.

Test coverage:
- Event sending and polling for responses
- Streaming event responses
- Task creation and message polling

Prerequisites:
    - AgentEx services running (make dev)
    - Agent running: agentex agents run --manifest manifest.yaml

Run tests:
    pytest tests/test_agent.py -v
"""

import asyncio
import pytest
import pytest_asyncio

from agentex.lib.testing.sessions import AsyncAgentTest
from agentex.lib.testing import stream_agent_response

from agentex.lib.testing import (
    async_test_agent,
    assert_valid_agent_response,
    assert_agent_response_contains,
)

AGENT_NAME = "ab000-hello-acp"

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
        # Poll for initial task creation message
        initial_response = await test_agent.poll_for_agent_response(timeout_seconds=15.0)
        assert_valid_agent_response(initial_response)
        assert_agent_response_contains(initial_response, "Hello! I've received your task")

        # Send a test message and validate response
        response = await test_agent.send_event("Hello, this is a test message!", timeout_seconds=30.0)
        # Validate latest response
        assert_valid_agent_response(response)
        assert_agent_response_contains(response, "Hello! I've received your message")


class TestStreamingEvents:
    """Test streaming event sending."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, test_agent: AsyncAgentTest):
        """Test sending an event and streaming the response."""
        user_message = "Hello, this is a test message!"

        # Flags to track what we've received
        task_creation_found = False
        user_echo_found = False
        agent_response_found = False
        all_events = []

        # Stream events
        async for event in stream_agent_response(test_agent.client, test_agent.task_id, timeout=30.0):
        #async for event in test_agent.send_event_and_stream(user_message, timeout_seconds=30.0):
            all_events.append(event)
            event_type = event.get("type")

            if event_type == "full":
                content = event.get("content", {})
                if content.get("content") is None:
                    continue  # Skip empty content

                if content.get("type") == "text" and content.get("author") == "agent":
                    # Check for initial task creation message
                    if "Hello! I've received your task" in content.get("content", ""):
                        task_creation_found = True
                    # Check for agent response to user message
                    elif "Hello! I've received your message" in content.get("content", ""):
                        agent_response_found = True

                elif content.get("type") == "text" and content.get("author") == "user":
                    # Check for user message echo (may or may not be present)
                    if content.get("content") == user_message:
                        user_echo_found = True

            # Exit early if we've found expected messages
            if task_creation_found and agent_response_found and user_echo_found:
                break

        print('all events', all_events)
        messages = await test_agent.client.messages.list(task_id=test_agent.task_id)
        print('all messages', messages)
        # Validate we saw expected messages
        assert task_creation_found, "Did not receive task creation message"
        assert agent_response_found, "Did not receive agent response to user message"
        # User echo is optional; no assert 
        assert user_echo_found, "User echo message not found"
        assert len(all_events) > 0, "Should receive events"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
