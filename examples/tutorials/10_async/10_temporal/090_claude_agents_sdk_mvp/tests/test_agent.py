import os

# import uuid
# import asyncio
import pytest
import pytest_asyncio

# from test_utils.async_utils import (
#     poll_messages,
#     stream_agent_response,
#     send_event_and_poll_yielding,
# )
from agentex import AsyncAgentex

# from agentex.types import TaskMessage
# from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
# from agentex.types.text_content_param import TextContentParam

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "claude-mvp-agent")


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
        pass


class TestStreamingEvents:
    """Test streaming event sending."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event and streaming the response."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
