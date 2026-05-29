"""Tests for the Temporal OpenAI Agents SDK local-sandbox agent.

This test suite validates that the agent actually runs shell commands in the
LOCAL sandbox (unix_local backend) via the Temporal sandbox bridge, by polling
for the agent's response:
- Ask for the Python version -> response contains "Python 3"
- Ask it to compute 21 * 2 with python3 -> response contains "42"

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: at120-openai-agents-local-sandbox)
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
AGENT_NAME = os.environ.get("AGENT_NAME", "at120-openai-agents-local-sandbox")


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


async def _create_task_and_await_welcome(client: AsyncAgentex, agent_id: str) -> str:
    """Create a task and wait for the workflow's welcome message; return the task id."""
    task_response = await client.agents.create_task(
        agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex)
    )
    task = task_response.result
    assert task is not None

    welcome_found = False
    async for message in poll_messages(
        client=client,
        task_id=task.id,
        timeout=30,
        sleep_interval=1.0,
    ):
        assert isinstance(message, TaskMessage)
        if message.content and message.content.type == "text" and message.content.author == "agent":
            welcome_found = True
            break
    assert welcome_found, "Task creation (welcome) message not found"
    return task.id


async def _send_and_collect_agent_text(
    client: AsyncAgentex, agent_id: str, task_id: str, user_message: str
) -> str:
    """Send a user message and accumulate the streamed agent text into a string."""
    final_message = None
    async for message in send_event_and_poll_yielding(
        client=client,
        agent_id=agent_id,
        task_id=task_id,
        user_message=user_message,
        timeout=60,
        sleep_interval=1.0,
        yield_updates=True,  # Get updates as streaming writes chunks
    ):
        if message.content and message.content.type == "text" and message.content.author == "agent":
            final_message = message
            if message.streaming_status == "DONE":
                break

    assert final_message is not None, "Should have received an agent text message"
    assert final_message.content is not None, "Final message should have content"
    return final_message.content.content or ""


class TestLocalSandboxEvents:
    """Test the Temporal local-sandbox OpenAI Agents SDK agent."""

    @pytest.mark.asyncio
    async def test_shell_python_version(self, client: AsyncAgentex, agent_id: str):
        """The agent should run `python3 --version` in the local sandbox.

        The sandbox runs on Python 3.12, so the real output contains "Python 3".
        """
        task_id = await _create_task_and_await_welcome(client, agent_id)
        text = await _send_and_collect_agent_text(
            client,
            agent_id,
            task_id,
            "Use your shell to print the Python version on this machine, then "
            "tell me what it is.",
        )
        assert text, "Expected a non-empty response from the sandbox agent."
        assert "Python 3" in text

    @pytest.mark.asyncio
    async def test_shell_compute(self, client: AsyncAgentex, agent_id: str):
        """The agent should use python3 in the sandbox to compute 21 * 2 == 42."""
        task_id = await _create_task_and_await_welcome(client, agent_id)
        text = await _send_and_collect_agent_text(
            client,
            agent_id,
            task_id,
            "Use python3 in your shell to compute 21 * 2 and tell me the result.",
        )
        assert text, "Expected a non-empty response from the sandbox agent."
        assert "42" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
