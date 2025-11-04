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
- AGENT_NAME: Name of the agent to test (default: ab030-tracing)
"""

import os

import pytest
import pytest_asyncio

from agentex import AsyncAgentex

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "ab030-tracing")


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
        # TODO: Create a task for this conversation
        # task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        # task = task_response.result
        # assert task is not None

        # TODO: Send an event and poll for response using the helper function
        # messages = []
        # async for message in send_event_and_poll_yielding(
        #     client=client,
        #     agent_id=agent_id,
        #     task_id=task.id,
        #     user_message="Your test message here",
        #     timeout=30,
        #     sleep_interval=1.0,
        # ):
        #     messages.append(message)

        # TODO: Validate the response
        # assert len(messages) > 0, "No response received from agent"
        # assert validate_text_in_response("expected text", messages)


class TestStreamingEvents:
    """Test streaming event sending."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event and streaming the response."""
        # TODO: Create a task for this conversation
        # task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        # task = task_response.result
        # assert task is not None

        # TODO: Send an event and stream the response using the helper function
        # all_events = []
        #
        # async def collect_stream_events():
        #     async for event in stream_agent_response(
        #         client=client,
        #         task_id=task.id,
        #         timeout=30,
        #     ):
        #         all_events.append(event)
        #
        # stream_task = asyncio.create_task(collect_stream_events())
        #
        # event_content = TextContentParam(type="text", author="user", content="Your test message here")
        # await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": event_content})
        #
        # await stream_task

        # TODO: Validate the streaming response
        # assert len(all_events) > 0, "No events received in streaming response"
        #
        # text_found = False
        # for event in all_events:
        #     content = event.get("content", {})
        #     if "expected text" in str(content).lower():
        #         text_found = True
        #         break
        # assert text_found, "Expected text not found in streaming response"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
