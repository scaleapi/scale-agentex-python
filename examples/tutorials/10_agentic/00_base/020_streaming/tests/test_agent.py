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
from test_utils.agentic import (
    stream_agent_response,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types import TaskMessage, TextContent
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
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=30,
            sleep_interval=1.0,
        ):
            messages.append(message)

        assert len(messages) > 0
        # the first message should be the agent re-iterating what the user sent
        assert isinstance(messages, List)
        assert len(messages) == 2
        first_message: TaskMessage = messages[0]
        assert first_message.content == TextContent(
            author="user",
            content=user_message,
            type="text",
        )

        second_message: TaskMessage = messages[1]
        assert second_message.content is not None
        assert second_message.content.author == "agent"

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

        async def stream_messages() -> None:
            async for event in stream_agent_response(
                client=client,
                task_id=task.id,
                timeout=15,
            ):
                all_events.append(event)

        stream_task = asyncio.create_task(stream_messages())

        event_content = TextContentParam(type="text", author="user", content=user_message)
        await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": event_content})

        # Wait for streaming to complete
        await stream_task

        # Validate we received events
        assert len(all_events) > 0, "No events received in streaming response"

        # Check for user message, full agent response, and delta messages
        user_message_found = False
        full_agent_message_found = False
        delta_messages_found = False

        for event in all_events:
            event_type = event.get("type")
            if event_type == "full":
                content = event.get("content", {})
                if content.get("content") == user_message and content.get("author") == "user":
                    user_message_found = True
                elif content.get("author") == "agent":
                    full_agent_message_found = True
            elif event_type == "delta":
                delta_messages_found = True

        assert user_message_found, "User message not found in stream"
        assert full_agent_message_found, "Full agent message not found in stream"
        assert delta_messages_found, "Delta messages not found in stream (streaming response expected)"

        # Verify the state has been updated
        await asyncio.sleep(1)  # wait for state to be updated
        states = await client.states.list(agent_id=agent_id, task_id=task.id)
        assert len(states) == 1
        state = states[0].state
        messages = state.get("messages", [])

        assert isinstance(messages, list)
        assert len(messages) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
