"""
Sample tests for AgentEx ACP agent.

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
- AGENT_NAME: Name of the agent to test (default: at030-custom-activities)
"""

import os
import asyncio
from typing import Any
from datetime import datetime, timezone
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from agentex import AsyncAgentex
from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.lib.types.acp import SendEventParams
from agentex.types.data_content import DataContent
from agentex.types.text_content import TextContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at030-custom-activities")


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

        # TODO: Poll for the initial task creation message (if your agent sends one)
        # async for message in poll_messages(
        #     client=client,
        #     task_id=task.id,
        #     timeout=30,
        #     sleep_interval=1.0,
        # ):
        #     assert isinstance(message, TaskMessage)
        #     if message.content and message.content.type == "text" and message.content.author == "agent":
        #         # Check for your expected initial message
        #         assert "expected initial text" in message.content.content
        #         break

        # TODO: Send an event and poll for response using the yielding helper function
        # user_message = "Your test message here"
        # async for message in send_event_and_poll_yielding(
        #     client=client,
        #     agent_id=agent_id,
        #     task_id=task.id,
        #     user_message=user_message,
        #     timeout=30,
        #     sleep_interval=1.0,
        # ):
        #     assert isinstance(message, TaskMessage)
        #     if message.content and message.content.type == "text" and message.content.author == "agent":
        #         # Check for your expected response
        #         assert "expected response text" in message.content.content
        #         break
        pass


class TestStreamingEvents:
    """Test streaming event sending."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event and streaming the response."""
        # TODO: Create a task for this conversation
        # task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        # task = task_response.result
        # assert task is not None

        # user_message = "Your test message here"

        # # Collect events from stream
        # all_events = []

        # async def collect_stream_events():
        #     async for event in stream_agent_response(
        #         client=client,
        #         task_id=task.id,
        #         timeout=30,
        #     ):
        #         all_events.append(event)

        # # Start streaming task
        # stream_task = asyncio.create_task(collect_stream_events())

        # # Send the event
        # event_content = TextContentParam(type="text", author="user", content=user_message)
        # await client.agents.send_event(agent_id=agent_id, params={"task_id": task.id, "content": event_content})

        # # Wait for streaming to complete
        # await stream_task

        # # TODO: Add your validation here
        # assert len(all_events) > 0, "No events received in streaming response"
        pass


# ---------------------------------------------------------------------------
# Offline signal-handler tests (no running agent, Temporal or network needed)
# ---------------------------------------------------------------------------

TASK_ID = "task-offline-1"
USER_TEXT = TextContent(author="user", content="Hello what can you do? EVENT NUM: 0")


def _send_event_params(content: Any) -> SendEventParams:
    """Real ``SendEventParams``, as the ACP delivers an ``event/send`` to the workflow signal."""
    now = datetime.now(timezone.utc)
    return SendEventParams(
        agent=Agent(id="agent-1", acp_type="async", name=AGENT_NAME, description="", created_at=now, updated_at=now),
        task=Task(id=TASK_ID),
        event=Event(id="event-1", agent_id="agent-1", task_id=TASK_ID, sequence_id=1, content=content),
    )


# Event content a caller can send that this handler must not act on: Event.content is
# optional, only text events are queued, and data events only act on known controls.
IGNORED_CONTENTS = [
    pytest.param(None, id="no-content"),
    pytest.param(DataContent(author="user", data={}), id="data-no-action"),
    pytest.param(DataContent(author="user", data={"unexpected": {"nested": [1, 2]}}), id="data-unexpected-keys"),
    pytest.param(DataContent(author="user", data={"clear_queue": "not-a-bool"}), id="data-invalid-value"),
    pytest.param(ReasoningContent(author="user", summary=["thinking"], type="reasoning"), id="reasoning"),
    pytest.param(
        ToolRequestContent(author="user", name="process", tool_call_id="call-1", arguments={"a": 1}),
        id="tool-request",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="process", tool_call_id="call-1", content={"k": "v"}),
        id="tool-response-dict",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="process", tool_call_id="call-1", content=[1, 2]),
        id="tool-response-list",
    ),
]


@contextmanager
def _mock_side_effects():
    """Mock what the handler can trigger, so nothing leaves the process."""
    with patch("project.workflow.adk.messages.create", new=AsyncMock()) as create, patch(
        "project.workflow.BatchProcessingUtils.handle_queue_clear", new=AsyncMock()
    ) as clear_queue, patch(
        "project.workflow.BatchProcessingUtils.handle_task_cancellation", new=AsyncMock()
    ) as cancel_tasks:
        yield create, clear_queue, cancel_tasks


class TestOfflineSignalHandler:
    """Unit tests for ``on_task_event_send``, called directly with real ``SendEventParams``."""

    @staticmethod
    def _workflow():
        from project.workflow import BATCH_SIZE, At030CustomActivitiesWorkflow

        # Build the instance without Temporal: skip __init__ and set what it would set.
        wf = At030CustomActivitiesWorkflow.__new__(At030CustomActivitiesWorkflow)
        wf.display_name = AGENT_NAME
        wf._incoming_queue = asyncio.Queue()
        wf._processing_tasks = []
        wf._batch_size = BATCH_SIZE
        wf._state = None
        return wf

    @pytest.mark.asyncio
    @pytest.mark.parametrize("content", IGNORED_CONTENTS)
    async def test_unprocessable_event_is_ignored(self, content):
        """Return without raising (that would wedge the task) and without side effects."""
        with _mock_side_effects() as (create, clear_queue, cancel_tasks):
            wf = self._workflow()
            await wf.on_task_event_send(_send_event_params(content))

        assert wf._incoming_queue.qsize() == 0
        create.assert_not_awaited()
        clear_queue.assert_not_awaited()
        cancel_tasks.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_text_event_is_queued_for_batch_processing(self):
        with _mock_side_effects() as (create, _clear_queue, _cancel_tasks):
            wf = self._workflow()
            await wf.on_task_event_send(_send_event_params(USER_TEXT))

        assert wf._incoming_queue.qsize() == 1
        assert wf._incoming_queue.get_nowait() == USER_TEXT
        create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_data_event_runs_the_queue_controls(self):
        content = DataContent(author="user", data={"clear_queue": True, "cancel_running_tasks": True})
        with _mock_side_effects() as (_create, clear_queue, cancel_tasks):
            wf = self._workflow()
            await wf.on_task_event_send(_send_event_params(content))

        clear_queue.assert_awaited_once_with(wf._incoming_queue, TASK_ID)
        cancel_tasks.assert_awaited_once_with(wf._processing_tasks, TASK_ID)

    @pytest.mark.asyncio
    async def test_text_event_on_a_full_queue_before_task_create_is_dropped(self):
        """A full queue drops the event without raising, even before on_task_create ran."""
        from project.workflow import MAX_QUEUE_DEPTH, At030CustomActivitiesWorkflow

        # The real __init__ this time: the state it leaves behind is what is under test.
        wf = At030CustomActivitiesWorkflow()
        for _ in range(MAX_QUEUE_DEPTH):
            wf._incoming_queue.put_nowait(USER_TEXT)

        with _mock_side_effects():
            await wf.on_task_event_send(_send_event_params(USER_TEXT))

        assert wf._incoming_queue.qsize() == MAX_QUEUE_DEPTH

    @pytest.mark.asyncio
    async def test_text_event_on_a_full_queue_is_counted_as_dropped(self):
        from project.workflow import MAX_QUEUE_DEPTH
        from project.shared_models import StateModel

        wf = self._workflow()
        wf._state = StateModel()
        for _ in range(MAX_QUEUE_DEPTH):
            wf._incoming_queue.put_nowait(USER_TEXT)

        with _mock_side_effects():
            await wf.on_task_event_send(_send_event_params(USER_TEXT))

        assert wf._incoming_queue.qsize() == MAX_QUEUE_DEPTH
        assert wf._state.total_events_dropped == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])