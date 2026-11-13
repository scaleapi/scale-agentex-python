# ci: touch to re-run tutorial integration tests for the openai-agents>=0.14.3 bump
"""
Sample tests for AgentEx ACP agent.

This test suite demonstrates how to test the main AgentEx API functions:
- Non-streaming event sending and polling
- Streaming event sending

The offline tests (``TestOfflineSignalHandler``) need no running agent: they call the
workflow's signal handler directly.

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Set the AGENTEX_API_BASE_URL environment variable if not using default
3. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: example-tutorial)
"""

import os
import uuid
from types import SimpleNamespace
from typing import Any
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from test_utils.async_utils import (
    poll_messages,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.lib.types.acp import SendEventParams
from agentex.types.data_content import DataContent
from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at060-open-ai-agents-sdk-hello-world")


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
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        # Poll for the initial task creation message
        task_creation_found = False
        async for message in poll_messages(
            client=client,
            task_id=task.id,
            timeout=30,
            sleep_interval=1.0,
        ):
            assert isinstance(message, TaskMessage)
            if message.content and message.content.type == "text" and message.content.author == "agent":
                # Check for the Haiku Assistant welcome message
                assert "Haiku Assistant" in message.content.content
                assert "Temporal" in message.content.content
                task_creation_found = True
                break

        assert task_creation_found, "Task creation message not found"

        # Send event and poll for response with streaming updates
        user_message = "Hello how is life?"

        # Use yield_updates=True to get all streaming chunks as they're written
        final_message = None
        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=30,
            sleep_interval=1.0,
            yield_updates=True,  # Get updates as streaming writes chunks
        ):
            if message.content and message.content.type == "text" and message.content.author == "agent":
                final_message = message

                # Stop polling once we get a DONE message
                if message.streaming_status == "DONE":
                    break

        # Verify the final message has content (the haiku)
        assert final_message is not None, "Should have received an agent message"
        assert final_message.content is not None, "Final message should have content"
        assert len(final_message.content.content) > 0, "Final message should have haiku content"


class TestStreamingEvents:
    """Test streaming event sending (backend verification via polling)."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """
        Streaming test placeholder.

        NOTE: SSE streaming is tested via the UI (agentex-ui subscribeTaskState).
        Backend streaming functionality is verified in test_send_event_and_poll.
        """
        pass


# ---------------------------------------------------------------------------
# Offline tests (always run -- no Temporal, network, or API keys needed)
# ---------------------------------------------------------------------------

# Event content a caller can legitimately send that this agent can't process.
NON_TEXT_CONTENTS = [
    pytest.param(None, id="no-content"),
    pytest.param(DataContent(author="user", data={}), id="data"),
    pytest.param(ReasoningContent(author="user", summary=["thinking"], content=["step"]), id="reasoning"),
    pytest.param(
        ToolRequestContent(author="user", name="lookup", tool_call_id="call-1", arguments={}), id="tool-request"
    ),
    pytest.param(
        ToolResponseContent(author="user", name="lookup", tool_call_id="call-1", content={"k": "v"}),
        id="tool-response-dict",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="lookup", tool_call_id="call-1", content=[1, 2]),
        id="tool-response-list",
    ),
]


class _FakeSpan:
    id = "span-offline-1"
    output: Any = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        pass


class _NoSpan:
    """What ``adk.tracing.span`` yields when the span could not be started."""

    async def __aenter__(self):
        return None

    async def __aexit__(self, *_a):
        pass


def _event_params(content: Any) -> SendEventParams:
    """Real SendEventParams, shaped like the payload the worker decodes from the signal."""
    now = datetime.now(timezone.utc)
    return SendEventParams(
        agent=Agent(id="agent-1", acp_type="async", name=AGENT_NAME, description="", created_at=now, updated_at=now),
        task=Task(id="task-offline-1"),
        event=Event(id="event-1", agent_id="agent-1", task_id="task-offline-1", sequence_id=1, content=content),
    )


def _workflow():
    """A workflow instance with the attributes __init__ and on_task_create would set."""
    from project.workflow import StateModel, At060OpenAiAgentsSdkHelloWorldWorkflow

    wf = At060OpenAiAgentsSdkHelloWorldWorkflow.__new__(At060OpenAiAgentsSdkHelloWorldWorkflow)
    wf.display_name = AGENT_NAME
    wf._complete_task = False
    wf._state = StateModel(input_list=[{"role": "user", "content": "earlier message"}], turn_number=1)
    wf._task_id = None
    wf._trace_id = None
    wf._parent_span_id = None
    return wf


@pytest.fixture
def side_effects():
    """Mock everything the handler calls that needs Temporal, the Agentex server or OpenAI."""
    with patch("project.workflow.adk.messages.create", new=AsyncMock()) as create, patch(
        "project.workflow.adk.tracing.span", return_value=_FakeSpan()
    ) as span, patch("project.workflow.Runner.run", new=AsyncMock(return_value=SimpleNamespace())) as run:
        yield SimpleNamespace(create=create, span=span, run=run)


class TestOfflineSignalHandler:
    """The RECEIVE_EVENT signal handler, called directly on a workflow instance.

    A signal handler must never raise on an event it can't process: Temporal would
    fail the workflow task and replay the signal forever, so the task would never
    handle another message.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("content", NON_TEXT_CONTENTS)
    async def test_non_text_event_is_ignored_without_side_effects(self, content, side_effects, caplog):
        wf = _workflow()
        state_before = wf._state.model_dump()
        params = _event_params(content)
        assert params.event.content is content

        await wf.on_task_event_send(params)

        side_effects.create.assert_not_awaited()
        side_effects.span.assert_not_called()
        side_effects.run.assert_not_awaited()
        assert wf._state.model_dump() == state_before
        assert (wf._task_id, wf._trace_id, wf._parent_span_id) == (None, None, None)
        assert "Ignoring non-text event for task task-offline-1" in caplog.text

    @pytest.mark.asyncio
    async def test_user_text_event_runs_the_agent(self, side_effects):
        wf = _workflow()
        content = TextContent(author="user", content="Hello how is life?")

        await wf.on_task_event_send(_event_params(content))

        side_effects.create.assert_awaited_once_with(task_id="task-offline-1", content=content)
        side_effects.run.assert_awaited_once()
        assert wf._state.turn_number == 2
        assert wf._state.input_list[-1] == {"role": "user", "content": "Hello how is life?"}
        assert wf._task_id == "task-offline-1"

    @pytest.mark.asyncio
    async def test_user_text_event_runs_when_tracing_yields_no_span(self, side_effects):
        # Tracing is best effort: when the span can't be started the turn must still run, not raise on span.output.
        side_effects.span.return_value = _NoSpan()
        wf = _workflow()

        await wf.on_task_event_send(_event_params(TextContent(author="user", content="Hello how is life?")))

        side_effects.run.assert_awaited_once()
        assert wf._state.turn_number == 2
        assert wf._parent_span_id is None

    @pytest.mark.asyncio
    async def test_event_before_state_is_initialised_waits_instead_of_raising(self, side_effects):
        from project.workflow import StateModel

        wf = _workflow()
        wf._state = None

        async def _wait_until_on_task_create_sets_state(condition, **_kw):
            assert not condition()
            wf._state = StateModel(input_list=[], turn_number=0)
            assert condition()

        with patch("project.workflow.workflow.wait_condition", new=_wait_until_on_task_create_sets_state):
            await wf.on_task_event_send(_event_params(TextContent(author="user", content="first message")))

        assert wf._state.turn_number == 1
        assert wf._state.input_list == [{"role": "user", "content": "first message"}]
        side_effects.create.assert_awaited_once()
        side_effects.run.assert_awaited_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
