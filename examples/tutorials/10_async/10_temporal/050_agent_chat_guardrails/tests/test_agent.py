"""
Sample tests for AgentEx ACP agent.

This test suite demonstrates how to test the main AgentEx API functions:
- Non-streaming event sending and polling
- Streaming event sending

It also unit-tests the workflow's signal handler offline (TestOfflineSignalHandler),
which needs no running agent, Temporal, network or API key.

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: at050-agent-chat-guardrails)
"""

import os
from types import SimpleNamespace
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
AGENT_NAME = os.environ.get("AGENT_NAME", "at050-agent-chat-guardrails")


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
# Offline signal-handler tests (no running agent, Temporal, network or API key)
# ---------------------------------------------------------------------------

TASK_ID = "task-offline-1"
USER_TEXT = TextContent(author="user", content="What is 2 + 2?")


def _send_event_params(content: Any) -> SendEventParams:
    """Real ``SendEventParams``, as the ACP delivers an ``event/send`` to the workflow signal."""
    now = datetime.now(timezone.utc)
    return SendEventParams(
        agent=Agent(id="agent-1", acp_type="async", name=AGENT_NAME, description="", created_at=now, updated_at=now),
        task=Task(id=TASK_ID),
        event=Event(id="event-1", agent_id="agent-1", task_id=TASK_ID, sequence_id=1, content=content),
    )


# Event content a caller can send that this handler must not process: Event.content is
# optional, only TextContent carries text, and the agent only answers user messages.
IGNORED_CONTENTS = [
    pytest.param(None, id="no-content"),
    pytest.param(DataContent(author="user", data={}), id="data"),
    pytest.param(ReasoningContent(author="user", summary=["thinking"], type="reasoning"), id="reasoning"),
    pytest.param(
        ToolRequestContent(author="user", name="calculator", tool_call_id="call-1", arguments={"a": 1}),
        id="tool-request",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="calculator", tool_call_id="call-1", content={"k": "v"}),
        id="tool-response-dict",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="calculator", tool_call_id="call-1", content=[1, 2]),
        id="tool-response-list",
    ),
    pytest.param(TextContent(author="agent", content="I am not the user"), id="agent-text"),
]


class _FakeSpan:
    id = "span-offline-1"
    output: Any = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


@contextmanager
def _mock_adk():
    """Mock the ``adk`` calls the handler makes, so nothing leaves the process."""
    run_result = SimpleNamespace(
        final_input_list=[
            {"role": "user", "content": USER_TEXT.content},
            {"role": "assistant", "content": "4"},
        ]
    )
    with patch("project.workflow.adk.messages.create", new=AsyncMock()) as create, patch(
        "project.workflow.adk.tracing.span", return_value=_FakeSpan()
    ) as span, patch(
        "project.workflow.adk.providers.openai.run_agent_streamed_auto_send",
        new=AsyncMock(return_value=run_result),
    ) as run_agent:
        yield create, span, run_agent


class TestOfflineSignalHandler:
    """Unit tests for ``on_task_event_send``, called directly with real ``SendEventParams``."""

    @staticmethod
    def _workflow():
        from project.workflow import StateModel, At050AgentChatGuardrailsWorkflow

        # Build the instance without Temporal: skip __init__ and set what it would set,
        # plus the state on_task_create initialises.
        wf = At050AgentChatGuardrailsWorkflow.__new__(At050AgentChatGuardrailsWorkflow)
        wf.display_name = AGENT_NAME
        wf._complete_task = False
        wf._state = StateModel(input_list=[], turn_number=0)
        return wf

    @pytest.mark.asyncio
    @pytest.mark.parametrize("content", IGNORED_CONTENTS)
    async def test_unprocessable_event_is_ignored(self, content):
        """Return without raising (that would wedge the task) and without side effects."""
        with _mock_adk() as (create, span, run_agent):
            wf = self._workflow()
            await wf.on_task_event_send(_send_event_params(content))

        create.assert_not_awaited()
        span.assert_not_called()
        run_agent.assert_not_awaited()
        assert wf._state.turn_number == 0
        assert wf._state.input_list == []

    @pytest.mark.asyncio
    async def test_user_text_event_runs_a_guarded_turn(self):
        """A user text event is echoed, added to the history and answered with guardrails on."""
        with _mock_adk() as (create, span, run_agent):
            wf = self._workflow()
            await wf.on_task_event_send(_send_event_params(USER_TEXT))

        assert wf._state.turn_number == 1
        span.assert_called_once()
        # The first message is the echo of the user's own message.
        assert create.await_args_list[0].kwargs["content"] == USER_TEXT
        run_agent.assert_awaited_once()
        kwargs = run_agent.await_args.kwargs
        assert kwargs["input_list"] == [{"role": "user", "content": USER_TEXT.content}]
        assert len(kwargs["input_guardrails"]) == 2
        assert len(kwargs["output_guardrails"]) == 2
        assert wf._state.input_list == run_agent.return_value.final_input_list

    @pytest.mark.asyncio
    async def test_event_before_state_is_initialised_waits_for_it(self):
        """An event handled before on_task_create has run waits for the state, not raises."""
        from project.workflow import StateModel

        wf = self._workflow()
        wf._state = None

        async def _wait_condition(condition):
            assert not condition()
            wf._state = StateModel(input_list=[], turn_number=0)  # on_task_create runs
            assert condition()

        with _mock_adk() as (create, _span, _run_agent), patch(
            "project.workflow.workflow.wait_condition", new=AsyncMock(side_effect=_wait_condition)
        ) as wait_condition:
            await wf.on_task_event_send(_send_event_params(USER_TEXT))

        wait_condition.assert_awaited_once()
        assert wf._state.turn_number == 1
        assert create.await_args_list[0].kwargs["content"] == USER_TEXT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])