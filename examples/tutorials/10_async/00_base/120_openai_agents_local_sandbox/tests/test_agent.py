"""Tests for the async OpenAI Agents SDK local-sandbox agent.

This test suite validates that the agent actually runs shell commands in the
LOCAL sandbox (unix_local backend) by polling for the agent's response:
- Ask for the Python version -> response contains "Python 3"
- Ask it to compute 21 * 2 with python3 -> response contains "42"

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: ab120-openai-agents-local-sandbox)
"""

import os
import uuid

import pytest
import pytest_asyncio
from test_utils.async_utils import send_event_and_poll_yielding

from agentex import AsyncAgentex
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest

AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "ab120-openai-agents-local-sandbox")


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


async def _send_and_collect_agent_text(
    client: AsyncAgentex, agent_id: str, task_id: str, user_message: str
) -> str:
    """Send a user message and accumulate all agent text responses into a string."""
    parts: list[str] = []
    async for message in send_event_and_poll_yielding(
        client=client,
        agent_id=agent_id,
        task_id=task_id,
        user_message=user_message,
        timeout=60,
        sleep_interval=1.0,
        yield_updates=True,
    ):
        content = message.content
        if content and content.type == "text" and content.author == "agent":
            if content.content and content.content not in parts:
                parts.append(content.content)
    return "\n".join(parts)


class TestLocalSandboxEvents:
    """Test the async local-sandbox OpenAI Agents SDK agent."""

    @pytest.mark.asyncio
    async def test_shell_python_version(self, client: AsyncAgentex, agent_id: str):
        """The agent should run `python3 --version` in the local sandbox.

        The sandbox runs on Python 3.12, so the real output contains "Python 3".
        """
        task_response = await client.agents.create_task(
            agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex)
        )
        task = task_response.result
        assert task is not None

        text = await _send_and_collect_agent_text(
            client,
            agent_id,
            task.id,
            "Use your shell to print the Python version on this machine, then "
            "tell me what it is.",
        )
        assert text, "Expected a non-empty response from the sandbox agent."
        assert "Python 3" in text

    @pytest.mark.asyncio
    async def test_shell_compute(self, client: AsyncAgentex, agent_id: str):
        """The agent should use python3 in the sandbox to compute 21 * 2 == 42."""
        task_response = await client.agents.create_task(
            agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex)
        )
        task = task_response.result
        assert task is not None

        text = await _send_and_collect_agent_text(
            client,
            agent_id,
            task.id,
            "Use python3 in your shell to compute 21 * 2 and tell me the result.",
        )
        assert text, "Expected a non-empty response from the sandbox agent."
        assert "42" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
