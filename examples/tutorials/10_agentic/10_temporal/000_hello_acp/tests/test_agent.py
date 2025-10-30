"""
Sample tests for AgentEx ACP agent (Temporal version).

This test suite demonstrates how to test the main AgentEx API functions:
- Non-streaming event sending and polling
- Streaming event sending

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: at000-hello-acp)
"""

import os
import uuid
import asyncio

import pytest
import pytest_asyncio
from test_utils.agentic import (
    poll_messages,
    stream_agent_response,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types import TaskMessage
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
from agentex.types.text_content_param import TextContentParam

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at000-hello-acp")


@pytest_asyncio.fixture
async def client():
    """Create an AgentEx client instance for testing."""
    client = AsyncAgentex(base_url=AGENTEX_API_BASE_URL)
    yield client
    await client.close()


@pytest.fixture
def agent_name():
    """Return the agent name for testing."""
    return AGENT_NAME


@pytest_asyncio.fixture
async def agent_id(client: AsyncAgentex, agent_name):
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

        # Poll for the initial task creation message
        async for message in poll_messages(
            client=client,
            task_id=task.id,
            timeout=30,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            if message.content and message.content.type == "text" and message.content.author == "agent":
                assert "Hello! I've received your task" in message.content.content
                break
        
        await asyncio.sleep(1.5)
        # Send an event and poll for response
        user_message = "Hello, this is a test message!"
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=30,
            sleep_interval=1.0,
        ):
            if message.content and message.content.type == "text" and message.content.author == "agent":
                assert "Hello! I've received your message" in message.content.content
                break


class TestStreamingEvents:
    """Test streaming event sending."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event and streaming the response."""
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        user_message = "Hello, this is a test message!"

        # Collect events from stream
        all_events = []

        # Flags to track what we've received
        task_creation_found = False
        user_echo_found = False
        agent_response_found = False

        async def collect_stream_events(): #noqa: ANN101
            nonlocal task_creation_found, user_echo_found, agent_response_found

            async for event in stream_agent_response(
                client=client,
                task_id=task.id,
                timeout=30,
            ):
                # Check events as they arrive
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
                            # Agent response should come after user echo
                            assert user_echo_found, "Agent response arrived before user message echo (incorrect order)"
                            agent_response_found = True
                    elif content.get("type") == "text" and content.get("author") == "user":
                        # Check for user message echo
                        if content.get("content") == user_message:
                            user_echo_found = True

                # Exit early if we've found all expected messages
                if task_creation_found and user_echo_found and agent_response_found:
                    break

            assert task_creation_found, "Task creation message not found in stream"
            assert user_echo_found, "User message echo not found in stream"
            assert agent_response_found, "Agent response not found in stream"


        # Start streaming task
        stream_task = asyncio.create_task(collect_stream_events())

        # Send the event
        event_content = TextContentParam(type="text", author="user", content=user_message)
        await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": event_content})

        # Wait for streaming to complete
        await stream_task

if __name__ == "__main__":
    pytest.main([__file__, "-v"])