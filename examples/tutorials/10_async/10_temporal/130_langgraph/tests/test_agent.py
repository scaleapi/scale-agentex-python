"""Integration tests for the Temporal + LangGraph agent (live agent required).

These drive a *running* agent over the AgentEx API and verify that:
- the agent sends a welcome message on task creation,
- a weather question triggers a tool_request / tool_response round-trip
  (proving the LLM node ran as a Temporal activity and the tool node ran),
- the final answer reflects the tool output.

For fast, network-free coverage of the graph + human-in-the-loop logic, see
``test_graph_temporal.py``.

To run:
1. Start the agent (worker + ACP server): ``agentex agents run --manifest manifest.yaml``
2. Set AGENTEX_API_BASE_URL if not using the default
3. ``pytest tests/test_agent.py -v``
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

AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at130-langgraph")


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
    """The Temporal-backed LangGraph agent responds and uses tools."""

    @pytest.mark.asyncio
    async def test_send_event_and_poll(self, client: AsyncAgentex, agent_id: str):
        """Create a task, ask about weather, verify the tool round-trip."""
        task_response = await client.agents.create_task(
            agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex)
        )
        task = task_response.result
        assert task is not None

        # Wait for the welcome message from on_task_create
        task_creation_found = False
        async for message in poll_messages(
            client=client, task_id=task.id, timeout=30, sleep_interval=1.0
        ):
            assert isinstance(message, TaskMessage)
            if (
                message.content
                and message.content.type == "text"
                and message.content.author == "agent"
            ):
                task_creation_found = True
                break
        assert task_creation_found, "Task creation welcome message not found"

        # Ask about weather — the agent (LangGraph node, as a Temporal activity)
        # should call get_weather.
        seen_tool_request = False
        seen_tool_response = False
        final_message = None
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message="What is the weather in San Francisco? Use your tool.",
            timeout=60,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)

            if message.content and message.content.type == "tool_request":
                seen_tool_request = True
            if message.content and message.content.type == "tool_response":
                seen_tool_response = True

            if (
                message.content
                and message.content.type == "text"
                and message.content.author == "agent"
            ):
                final_message = message
                content_length = len(getattr(message.content, "content", "") or "")
                if getattr(message, "streaming_status", None) in (None, "DONE") and content_length > 0:
                    if seen_tool_response:
                        break

        assert seen_tool_request, "Expected a tool_request (agent calling get_weather)"
        assert seen_tool_response, "Expected a tool_response (get_weather result)"
        assert final_message is not None, "Expected a final agent text message"
        final_text = (
            getattr(final_message.content, "content", None) if final_message.content else None
        )
        assert isinstance(final_text, str) and len(final_text) > 0
        # get_weather always returns "72°F" — the response should mention it.
        assert "72" in final_text, "Expected weather response to mention 72°F"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
