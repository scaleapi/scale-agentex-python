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
- AGENT_NAME: Name of the agent to test (default: example-tutorial)
"""

import os
import uuid

import pytest
import pytest_asyncio
from test_utils.async_utils import (
    poll_messages,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types.task_message import TaskMessage
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at060-open-ai-agents-sdk-hello-world")


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
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Poll for the initial task creation message
        task_creation_found = False
        async for message in poll_messages(
            client=client,
            task_id=task.id,
            timeout=30,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            if message.content and message.content.type == "text" and message.content.author == "agent":
                # Check for the Haiku Assistant welcome message
                assert "Haiku Assistant" in message.content.content
                assert "Temporal" in message.content.content
                task_creation_found = True
                break

        assert task_creation_found, "Task creation message not found"

        # Send event and poll for response with streaming updates
        user_message = "Hello how is life?"

        # Use yield_updates=True to get all streaming chunks as they're written
        final_message = None
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=30,
            sleep_interval=1.0,
            yield_updates=True,  # Get updates as streaming writes chunks
        ):
            if message.content and message.content.type == "text" and message.content.author == "agent":
                final_message = message

                # Stop polling once we get a DONE message
                if message.streaming_status == "DONE":
                    break

        # Verify the final message has content (the haiku)
        assert final_message is not None, "Should have received an agent message"
        assert final_message.content is not None, "Final message should have content"
        assert len(final_message.content.content) > 0, "Final message should have haiku content"


class TestStreamingEvents:
    """Test streaming event sending (backend verification via polling)."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """
        Streaming test placeholder.

        NOTE: SSE streaming is tested via the UI (agentex-ui subscribeTaskState).
        Backend streaming functionality is verified in test_send_event_and_poll.
        """
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
