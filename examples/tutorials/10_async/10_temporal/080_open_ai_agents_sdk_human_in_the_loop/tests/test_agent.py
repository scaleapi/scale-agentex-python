"""
Sample tests for AgentEx ACP agent with Human-in-the-Loop workflow.

This test suite demonstrates how to test human-in-the-loop workflows:
- Non-streaming event sending and polling
- Detecting when workflow is waiting for human approval
- Sending Temporal signals to approve/reject
- Verifying workflow completes after approval

The offline tests (``TestOfflineSignalHandler``) need no running agent or Temporal:
they call the workflow's signal handler directly.

To run these tests:
1. Make sure the agent is running (via docker-compose or `agentex agents run`)
2. Make sure Temporal is running (localhost:7233)
3. Set the AGENTEX_API_BASE_URL environment variable if not using default
4. Run: pytest test_agent.py -v

Configuration:
- AGENTEX_API_BASE_URL: Base URL for the AgentEx server (default: http://localhost:5003)
- AGENT_NAME: Name of the agent to test (default: example-tutorial)
- TEMPORAL_ADDRESS: Temporal server address (default: localhost:7233)
"""

import os
import uuid
import asyncio
from types import SimpleNamespace
from typing import Any
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

# Temporal imports for signaling child workflows
from temporalio.client import Client as TemporalClient
from test_utils.async_utils import (
    poll_messages,
    send_event_and_poll_yielding,
)

from agentex import AsyncAgentex
from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.protocol.acp import SendEventParams
from agentex.types.data_content import DataContent
from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at080-open-ai-agents-sdk-human-in-the-loop")
TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")


@pytest_asyncio.fixture
async def client():
    """Create an AsyncAgentex client instance for testing."""
    client = AsyncAgentex(base_url=AGENTEX_API_BASE_URL)
    yield client
    await client.close()


@pytest_asyncio.fixture
async def temporal_client():
    """Create a Temporal client for sending signals to workflows."""
    client = await TemporalClient.connect(TEMPORAL_ADDRESS)
    yield client
    # Temporal client doesn't need explicit close in recent versions


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
    """Test non-streaming event sending and polling with human-in-the-loop."""

    @pytest.mark.asyncio
    async def test_send_event_and_poll_with_human_approval(self, client: AsyncAgentex, agent_id: str, temporal_client: TemporalClient):
        """Test sending an event that triggers human approval workflow."""
        # Create a task for this conversation
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
                # Check for the initial acknowledgment message
                assert "task" in message.content.content.lower() or "received" in message.content.content.lower()
                task_creation_found = True
                break

        assert task_creation_found, "Task creation message not found"

        # Send an event asking to confirm an order (triggers human-in-the-loop)
        user_message = "Please confirm my order"

        # Track what we've seen to ensure human-in-the-loop flow happened
        seen_tool_request = False
        seen_tool_response = False
        found_final_response = False
        approval_signal_sent = False

        async for message in send_event_and_poll_yielding(
            client=client,
            agent_id=agent_id,
            task_id=task.id,
            user_message=user_message,
            timeout=120,  # Longer timeout for human-in-the-loop
            sleep_interval=1.0,
            yield_updates=True,  # Get all streaming chunks
        ):
            assert isinstance(message, TaskMessage)

            # Track tool_request messages (agent calling wait_for_confirmation)
            if message.content and message.content.type == "tool_request":
                seen_tool_request = True

                if not approval_signal_sent:
                    # Send signal to child workflow to approve the order
                    # The child workflow ID is fixed as "child-workflow-id" (see tools.py)
                    # Give Temporal a brief moment to materialize the child workflow
                    await asyncio.sleep(1)
                    try:
                        handle = temporal_client.get_workflow_handle("child-workflow-id")
                        await handle.signal("fulfill_order_signal", True)
                        approval_signal_sent = True
                    except Exception as e:
                        # It's okay if the workflow completed before we could signal it.
                        _ = e

            # Track tool_response messages (child workflow completion)
            if message.content and message.content.type == "tool_response":
                seen_tool_response = True
                # If we already saw DONE but were waiting for tool_response, exit now
                if found_final_response:
                    break

            # Track agent text messages and their streaming updates
            if message.content and message.content.type == "text" and message.content.author == "agent":
                content_length = len(message.content.content) if message.content.content else 0

                # Stop when we get DONE with content, but only if tool_response
                # is already visible. The DONE text can be persisted before the
                # lifecycle activity persists tool_response to the message list.
                if message.streaming_status == "DONE" and content_length > 0:
                    found_final_response = True
                    if not seen_tool_request or seen_tool_response:
                        break

        # Verify that we saw the complete flow: tool_request -> human approval -> tool_response -> final answer
        assert seen_tool_request, "Expected to see tool_request message (agent calling wait_for_confirmation)"
        assert seen_tool_response, "Expected to see tool_response message (child workflow completion after approval)"
        assert found_final_response, "Expected to see final text response after human approval"


class TestStreamingEvents:
    """Test streaming event sending (backend verification via polling)."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """
        Streaming test placeholder.

        NOTE: SSE streaming is tested via the UI (agentex-ui subscribeTaskState).
        Backend streaming functionality is verified in test_send_event_and_poll_with_human_approval.
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
    from project.workflow import StateModel, At080OpenAiAgentsSdkHumanInTheLoopWorkflow

    wf = At080OpenAiAgentsSdkHumanInTheLoopWorkflow.__new__(At080OpenAiAgentsSdkHumanInTheLoopWorkflow)
    wf.display_name = AGENT_NAME
    wf._complete_task = False
    wf._state = StateModel(input_list=[{"role": "user", "content": "earlier message"}], turn_number=1)
    wf._pending_confirmation = asyncio.Queue()
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
        content = TextContent(author="user", content="Please confirm my order")

        await wf.on_task_event_send(_event_params(content))

        side_effects.create.assert_awaited_once_with(task_id="task-offline-1", content=content)
        side_effects.run.assert_awaited_once()
        assert wf._state.turn_number == 2
        assert wf._state.input_list[-1] == {"role": "user", "content": "Please confirm my order"}
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
