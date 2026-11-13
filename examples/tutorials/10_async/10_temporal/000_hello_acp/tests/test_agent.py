"""
Sample tests for AgentEx ACP agent (Temporal version).

This test suite demonstrates how to test the main AgentEx API functions:
- Non-streaming event sending and polling
- Streaming event sending

It also unit-tests the workflow's signal handler offline (TestOfflineSignalHandler),
which needs no running agent, Temporal or network.

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: at000-hello-acp)
"""

import os
import uuid
import asyncio
from typing import Any
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from test_utils.async_utils import (
    poll_messages,
    stream_agent_response,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types import TaskMessage
from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.lib.types.acp import SendEventParams
from agentex.types.data_content import DataContent
from agentex.types.text_content import TextContent
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.text_content_param import TextContentParam
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at000-hello-acp")


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
        # Create a task for this conversation
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        task_creation_found = False
        async for message in poll_messages(
            client=client,
            task_id=task.id,
            timeout=30,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            if message.content and message.content.type == "text" and message.content.author == "agent":
                assert "Hello! I've received your task" in message.content.content
                task_creation_found = True
                break

        assert task_creation_found, "Task creation message not found"
        await asyncio.sleep(1.5)

        # Send an event and poll for response
        user_message = "Hello, this is a test message!"
        agent_response_found = False
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=30,
            sleep_interval=1.0,
        ):
            if message.content and message.content.type == "text" and message.content.author == "agent":
                assert "Hello! I've received your message" in message.content.content
                agent_response_found = True
                break

        assert agent_response_found, "Agent response not found"


class TestStreamingEvents:
    """Test streaming event sending."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event and streaming the response."""
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        task_creation_found = False
        async for message in poll_messages(
            client=client,
            task_id=task.id,
            timeout=30,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            if message.content and message.content.type == "text" and message.content.author == "agent":
                assert "Hello! I've received your task" in message.content.content
                task_creation_found = True
                break

        assert task_creation_found, "Task creation message not found"

        user_message = "Hello, this is a test message!"

        # Collect events from stream
        all_events: list[dict[str, Any]] = []

        # Flags to track what we've received
        user_echo_found = False
        agent_response_found = False
        stream_timeout = 30

        async def stream_messages() -> None:
            nonlocal user_echo_found, agent_response_found
            async for event in stream_agent_response(
                client=client,
                task_id=task.id,
                timeout=stream_timeout,
            ):
                # Check events as they arrive
                event_type = event.get("type")
                if event_type == "full":
                    content = event.get("content", {})
                    if content.get("content") is None:
                        continue  # Skip empty content
                    if content.get("type") == "text" and content.get("author") == "agent":
                        # Check for agent response to user message
                        if "Hello! I've received your message" in content.get("content", ""):
                            # Agent response should come after user echo
                            assert user_echo_found, "Agent response arrived before user message echo (incorrect order)"
                            agent_response_found = True
                    elif content.get("type") == "text" and content.get("author") == "user":
                        # Check for user message echo
                        if content.get("content") == user_message:
                            user_echo_found = True
                elif event_type == "done":
                    break

                # Exit early if we've found all expected messages
                if user_echo_found and agent_response_found:
                    break

        stream_task = asyncio.create_task(stream_messages())

        # Send the event
        event_content = TextContentParam(type="text", author="user", content=user_message)
        await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": event_content})
        await stream_task

        # Verify all expected messages were received (fail if stream ended without finding them)

        assert user_echo_found, "User message echo not found in stream"
        assert agent_response_found, "Agent response not found in stream"


# ---------------------------------------------------------------------------
# Offline signal-handler tests (no running agent, Temporal or network needed)
# ---------------------------------------------------------------------------

TASK_ID = "task-offline-1"


def _send_event_params(content: Any) -> SendEventParams:
    """Real ``SendEventParams``, as the ACP delivers an ``event/send`` to the workflow signal."""
    now = datetime.now(timezone.utc)
    return SendEventParams(
        agent=Agent(id="agent-1", acp_type="async", name=AGENT_NAME, description="", created_at=now, updated_at=now),
        task=Task(id=TASK_ID),
        event=Event(id="event-1", agent_id="agent-1", task_id=TASK_ID, sequence_id=1, content=content),
    )


# Every content type a caller can send. This handler only echoes the content back, so
# all of them are valid input: the one thing it cannot echo is an event with no content.
ECHOED_CONTENTS = [
    pytest.param(TextContent(author="user", content="Hello!"), id="text"),
    pytest.param(DataContent(author="user", data={}), id="data"),
    pytest.param(ReasoningContent(author="user", summary=["thinking"], type="reasoning"), id="reasoning"),
    pytest.param(
        ToolRequestContent(author="user", name="get_weather", tool_call_id="call-1", arguments={"city": "Paris"}),
        id="tool-request",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="get_weather", tool_call_id="call-1", content={"k": "v"}),
        id="tool-response-dict",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="get_weather", tool_call_id="call-1", content=[1, 2]),
        id="tool-response-list",
    ),
]


class TestOfflineSignalHandler:
    """Unit tests for ``on_task_event_send`` that need no running agent, Temporal or network.

    The handler is called directly with real ``SendEventParams``; ``adk.messages.create``
    is mocked, so nothing leaves the process.
    """

    @staticmethod
    def _workflow():
        from project.workflow import At000HelloAcpWorkflow

        # Build the instance without Temporal: skip __init__ and set what it would set.
        wf = At000HelloAcpWorkflow.__new__(At000HelloAcpWorkflow)
        wf.display_name = AGENT_NAME
        wf._complete_task = False
        return wf

    @pytest.mark.asyncio
    async def test_event_without_content_is_ignored(self):
        """No content: return without raising (that would wedge the task) and send nothing."""
        with patch("project.workflow.adk.messages.create", new=AsyncMock()) as create:
            wf = self._workflow()
            await wf.on_task_event_send(_send_event_params(None))

        create.assert_not_awaited()
        assert wf._complete_task is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("content", ECHOED_CONTENTS)
    async def test_event_is_echoed_then_answered(self, content):
        """Any content type is echoed back unchanged, then the agent replies."""
        with patch("project.workflow.adk.messages.create", new=AsyncMock()) as create:
            wf = self._workflow()
            await wf.on_task_event_send(_send_event_params(content))

        assert create.await_count == 2
        echo, reply = create.await_args_list
        assert echo.kwargs == {"task_id": TASK_ID, "content": content}
        assert reply.kwargs["task_id"] == TASK_ID
        assert isinstance(reply.kwargs["content"], TextContent)
        assert reply.kwargs["content"].author == "agent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])