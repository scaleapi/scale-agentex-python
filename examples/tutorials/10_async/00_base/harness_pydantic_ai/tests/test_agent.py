"""Live tests for the async harness Pydantic AI agent.

These tests require a running agent (server + deployed agent) and exercise the
unified-surface async handler end-to-end over the wire. They mirror the
``110_pydantic_ai`` async tutorial tests but target this harness agent.

Offline coverage of the same wiring (TestModel + fake streaming/tracing) lives
in ``tests/lib/core/harness/test_harness_pydantic_ai_async.py`` in the SDK repo.

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: ab-harness-pydantic-ai)
"""

import os

import pytest
import pytest_asyncio

from agentex import AsyncAgentex
from agentex.types import TextContentParam
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
from agentex.lib.sdk.fastacp.base.base_acp_server import uuid

AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "ab-harness-pydantic-ai")


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
    """Test non-streaming event sending through the unified auto_send_turn path."""

    @pytest.mark.asyncio
    async def test_send_event(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event to the async harness Pydantic AI agent."""
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        event_content = TextContentParam(
            type="text",
            author="user",
            content="Hello! What can you help me with?",
        )
        await client.agents.send_event(
            agent_id=agent_id,
            params={"task_id": task.id, "content": event_content},
        )

    @pytest.mark.asyncio
    async def test_tool_calling(self, client: AsyncAgentex, agent_id: str):
        """Test that the agent can use tools (e.g., weather tool)."""
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        event_content = TextContentParam(
            type="text",
            author="user",
            content="What's the weather in San Francisco?",
        )
        await client.agents.send_event(
            agent_id=agent_id,
            params={"task_id": task.id, "content": event_content},
        )


class TestStreamingEvents:
    """Test streaming event sending."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event and streaming the response."""
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        event_content = TextContentParam(
            type="text",
            author="user",
            content="Tell me a short joke.",
        )
        await client.agents.send_event(
            agent_id=agent_id,
            params={"task_id": task.id, "content": event_content},
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
