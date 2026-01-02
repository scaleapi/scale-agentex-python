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
AGENT_NAME = os.environ.get("AGENT_NAME", "at070-open-ai-agents-sdk-tools")


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
                # Check for the initial acknowledgment message
                assert "task" in message.content.content.lower() or "received" in message.content.content.lower()
                task_creation_found = True
                break

        assert task_creation_found, "Task creation message not found"

        # Send an event asking about the weather in NYC and poll for response with streaming
        user_message = "What is the weather in New York City?"

        # Track what we've seen to ensure tool calls happened
        seen_tool_request = False
        seen_tool_response = False
        final_message = None
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=60,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)

            # Track tool_request messages (agent calling get_weather)
            if message.content and message.content.type == "tool_request":
                seen_tool_request = True

            # Track tool_response messages (get_weather result)
            if message.content and message.content.type == "tool_response":
                seen_tool_response = True

            # Track agent text messages and their streaming updates
            if message.content and message.content.type == "text" and message.content.author == "agent":
                agent_text = getattr(message.content, "content", "") or ""
                content_length = len(str(agent_text))
                final_message = message

                # Stop when we get DONE status
                if message.streaming_status == "DONE" and content_length > 0:
                    break

        # Verify we got all the expected pieces
        assert seen_tool_request, "Expected to see tool_request message (agent calling get_weather)"
        assert seen_tool_response, "Expected to see tool_response message (get_weather result)"
        assert final_message is not None, "Expected to see final agent text message"
        final_text = getattr(final_message.content, "content", None) if final_message.content else None
        assert isinstance(final_text, str) and len(final_text) > 0, "Final message should have content"

        # Check that the response contains the temperature (22 degrees)
        # The get_weather activity returns "The weather in New York City is 22 degrees Celsius"
        assert "22" in final_text, "Expected weather response to contain temperature (22 degrees)"


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