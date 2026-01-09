"""
Sample tests for AgentEx ACP agent.

This test suite demonstrates how to test the main AgentEx API functions:
- Non-streaming event sending and polling
- Streaming event sending

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: ab020-streaming)
"""

import os
import uuid
import asyncio
from typing import List

import pytest
import pytest_asyncio
from test_utils.async_utils import (
    stream_agent_response,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
from agentex.types.text_content_param import TextContentParam

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "ab020-streaming")


@pytest_asyncio.fixture
async def client():
    """Create an AsyncAgentex client instance for testing."""
    client = AsyncAgentex(base_url=AGENTEX_API_BASE_URL)
    yield client
    await client.close()


@pytest.fixture
def agent_name():
    """Return the agent name for testing."""
    return AGENT_NAME


@pytest_asyncio.fixture
async def agent_id(client, agent_name):
    """Retrieve the agent ID based on the agent name."""
    agents = await client.agents.list()
    for agent in agents:
        if agent.name == agent_name:
            return agent.id
    raise ValueError(f"Agent with name {agent_name} not found.")


class TestNonStreamingEvents:
    """Test non-streaming event sending and polling."""

    @pytest.mark.asyncio
    async def test_send_event_and_poll(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event and polling for the response."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        await asyncio.sleep(1)  # wait for state to be initialized
        states = await client.states.list(agent_id=agent_id, task_id=task.id)
        assert len(states) == 1

        state = states[0].state
        assert state is not None
        messages = state.get("messages", [])
        assert isinstance(messages, List)
        assert len(messages) == 1  # initial message
        message = messages[0]
        assert message == {
            "role": "system",
            "content": "You are a helpful assistant that can answer questions.",
        }

        user_message = "Hello! Here is my test message"
        messages = []

        # Flags to track what we've received
        user_message_found = False
        agent_response_found = False
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=30,
            sleep_interval=1.0,
            yield_updates=False,
        ):
            messages.append(message)

            # Validate messages as they come in
            if message.content and hasattr(message.content, "author"):
                if message.content.author == "user" and message.content.content == user_message:
                    user_message_found = True
                elif message.content.author == "agent":
                    # Agent response should come after user message
                    assert user_message_found, "Agent response arrived before user message"
                    agent_response_found = True

            # Exit early if we've found all expected messages
            if user_message_found and agent_response_found:
                break

        # Validate we received expected messages
        assert len(messages) >= 2, "Expected at least 2 messages (user + agent)"
        assert user_message_found, "User message not found"
        assert agent_response_found, "Agent response not found"

        # assert the state has been updated
        await asyncio.sleep(1)  # wait for state to be updated
        states = await client.states.list(agent_id=agent_id, task_id=task.id)
        assert len(states) == 1
        state = states[0].state
        messages = state.get("messages", [])

        assert isinstance(messages, list)
        assert len(messages) == 3


class TestStreamingEvents:
    """Test streaming event sending."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event and streaming the response."""
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Check initial state
        await asyncio.sleep(1)  # wait for state to be initialized
        states = await client.states.list(agent_id=agent_id, task_id=task.id)
        assert len(states) == 1

        state = states[0].state
        assert state is not None
        messages = state.get("messages", [])
        assert isinstance(messages, List)
        assert len(messages) == 1  # initial message
        message = messages[0]
        assert message == {
            "role": "system",
            "content": "You are a helpful assistant that can answer questions.",
        }
        user_message = "Hello! This is my first message. Can you please tell me something interesting about yourself?"

        # Collect events from stream
        all_events = []

        # Flags to track what we've received
        user_message_found = False
        full_agent_message_found = False
        delta_messages_found = False
        async def stream_messages() -> None:
            nonlocal user_message_found, full_agent_message_found, delta_messages_found
            async for event in stream_agent_response(
                client=client,
                task_id=task.id,
                timeout=15,
            ):
                all_events.append(event)

                # Check events as they arrive
                event_type = event.get("type")
                if event_type == "full":
                    content = event.get("content", {})
                    if content.get("content") == user_message and content.get("author") == "user":
                        user_message_found = True
                    elif content.get("author") == "agent":
                        full_agent_message_found = True
                elif event_type == "delta":
                    delta_messages_found = True
                elif event_type == "done":
                    break

                # Exit early if we've found all expected messages
                if user_message_found and full_agent_message_found and delta_messages_found:
                    break

        stream_task = asyncio.create_task(stream_messages())
        event_content = TextContentParam(type="text", author="user", content=user_message)
        await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": event_content})
        await stream_task

        # Validate we received events
        assert len(all_events) > 0, "No events received in streaming response"
        assert user_message_found, "User message not found in stream"
        assert full_agent_message_found, "Full agent message not found in stream"
        assert delta_messages_found, "Delta messages not found in stream (streaming response expected)"

        # Verify the state has been updated
        await asyncio.sleep(1)  # wait for state to be updated
        states = await client.states.list(agent_id=agent_id, task_id=task.id)
        assert len(states) == 1
        state: dict[str, object] = states[0].state
        messages = state.get("messages", [])

        assert isinstance(messages, list)
        assert len(messages) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
