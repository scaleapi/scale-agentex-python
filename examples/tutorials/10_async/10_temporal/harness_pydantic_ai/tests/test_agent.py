"""Live tests for the Temporal harness Pydantic AI agent.

These tests require a running agent (Temporal + Redis + ACP server + worker) and
exercise the unified-surface event_stream_handler end-to-end over the wire. They
mirror the ``at110`` temporal tutorial tests but target this harness agent.

Offline coverage of the same wiring (TestModel + fake streaming/tracing) lives
in ``tests/lib/core/harness/test_harness_pydantic_ai_temporal.py`` in the SDK repo.

To run these tests:
1. Make sure the agent is running (worker + ACP server)
2. Set AGENTEX_API_BASE_URL if not using the default
3. Run: pytest tests/test_agent.py -v
"""

import os
import uuid

import pytest
import pytest_asyncio
from test_utils.async_utils import poll_messages, send_event_and_poll_yielding

from agentex import AsyncAgentex
from agentex.types.task_message import TaskMessage
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest

AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at-harness-pydantic-ai")


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
    """Test that the Temporal-backed harness agent responds and uses tools."""

    @pytest.mark.asyncio
    async def test_send_event_and_poll(self, client: AsyncAgentex, agent_id: str):
        """Drive a full turn: create task, send a weather question, verify tool round-trip."""
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Wait for the welcome message from on_task_create
        task_creation_found = False
        async for message in poll_messages(
            client=client,
            task_id=task.id,
            timeout=30,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            if message.content and message.content.type == "text" and message.content.author == "agent":
                task_creation_found = True
                break
        assert task_creation_found, "Task creation welcome message not found"

        # Ask about weather — the agent should call get_weather
        seen_tool_request = False
        seen_tool_response = False
        final_message = None
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message="What is the weather in San Francisco?",
            timeout=60,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)

            if message.content and message.content.type == "tool_request":
                seen_tool_request = True
            if message.content and message.content.type == "tool_response":
                seen_tool_response = True
                if final_message and getattr(final_message, "streaming_status", None) == "DONE":
                    break

            if message.content and message.content.type == "text" and message.content.author == "agent":
                final_message = message
                content_length = len(getattr(message.content, "content", "") or "")
                if message.streaming_status == "DONE" and content_length > 0:
                    if not seen_tool_request or seen_tool_response:
                        break

        assert seen_tool_request, "Expected a tool_request (agent calling get_weather)"
        assert seen_tool_response, "Expected a tool_response (get_weather result)"
        assert final_message is not None, "Expected a final agent text message"
        final_text = getattr(final_message.content, "content", None) if final_message.content else None
        assert isinstance(final_text, str) and len(final_text) > 0
        # The get_weather tool always returns "72°F" — the response should mention it.
        assert "72" in final_text, "Expected weather response to mention 72°F"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
