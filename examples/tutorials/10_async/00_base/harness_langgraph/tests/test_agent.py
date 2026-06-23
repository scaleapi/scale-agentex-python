"""
Tests for the async harness LangGraph agent.

Validates the unified harness surface (LangGraphTurn + UnifiedEmitter.auto_send_turn)
end-to-end against a live AgentEx server.

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: a-harness-langgraph)
"""

import os

import pytest
import pytest_asyncio

from agentex import AsyncAgentex
from agentex.types import TextContentParam
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
from agentex.lib.sdk.fastacp.base.base_acp_server import uuid

AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "a-harness-langgraph")


@pytest_asyncio.fixture
async def client():
    client = AsyncAgentex(base_url=AGENTEX_API_BASE_URL)
    yield client
    await client.close()


@pytest.fixture
def agent_name():
    return AGENT_NAME


@pytest_asyncio.fixture
async def agent_id(client, agent_name):
    agents = await client.agents.list()
    for agent in agents:
        if agent.name == agent_name:
            return agent.id
    raise ValueError(f"Agent with name {agent_name} not found.")


class TestNonStreamingEvents:
    @pytest.mark.asyncio
    async def test_send_event(self, client: AsyncAgentex, agent_id: str):
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
    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
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
