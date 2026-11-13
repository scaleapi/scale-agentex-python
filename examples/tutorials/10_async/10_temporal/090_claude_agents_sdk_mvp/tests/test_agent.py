import os
from types import SimpleNamespace
from typing import Any
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

# import uuid
# import asyncio
import pytest
import pytest_asyncio

# from test_utils.async_utils import (
#     poll_messages,
#     stream_agent_response,
#     send_event_and_poll_yielding,
# )
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

# from agentex.types import TaskMessage
# from agentex.types.agent_rpc_params import ParamsCreateTaskRequest
# from agentex.types.text_content_param import TextContentParam

# Configuration from environment variables
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "claude-mvp-agent")


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
        pass


class TestStreamingEvents:
    """Test streaming event sending."""

    @pytest.mark.asyncio
    async def test_send_event_and_stream(self, client: AsyncAgentex, agent_id: str):
        """Test sending an event and streaming the response."""
        pass


# ---------------------------------------------------------------------------
# Offline tests (always run -- no Temporal, network, or API keys needed)
# ---------------------------------------------------------------------------

WORKSPACE = "/workspaces/task-offline-1"

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
    from project.workflow import StateModel, ClaudeMvpWorkflow

    wf = ClaudeMvpWorkflow.__new__(ClaudeMvpWorkflow)
    wf.display_name = AGENT_NAME
    wf._complete_task = False
    wf._state = StateModel(claude_session_id="session-earlier", turn_number=1)
    wf._task_id = None
    wf._trace_id = None
    wf._parent_span_id = None
    wf._workspace_path = WORKSPACE
    return wf


@pytest.fixture
def side_effects():
    """Mock everything the handler calls that needs Temporal, the Agentex server or Claude."""
    with patch("project.workflow.adk.messages.create", new=AsyncMock()) as create, patch(
        "project.workflow.adk.tracing.span", return_value=_FakeSpan()
    ) as span, patch(
        "project.workflow.workflow.execute_activity", new=AsyncMock(return_value={"session_id": "session-new"})
    ) as execute_activity:
        yield SimpleNamespace(create=create, span=span, execute_activity=execute_activity)


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
        side_effects.execute_activity.assert_not_awaited()
        assert wf._state.model_dump() == state_before
        assert (wf._task_id, wf._trace_id, wf._parent_span_id) == (None, None, None)
        assert "Ignoring non-text event for task task-offline-1" in caplog.text

    @pytest.mark.asyncio
    async def test_user_text_event_runs_claude(self, side_effects):
        wf = _workflow()
        content = TextContent(author="user", content="Create a hello.py file")

        await wf.on_task_event_send(_event_params(content))

        side_effects.create.assert_awaited_once_with(task_id="task-offline-1", content=content)
        side_effects.execute_activity.assert_awaited_once()
        prompt, workspace, *_ = side_effects.execute_activity.await_args.kwargs["args"]
        assert (prompt, workspace) == ("Create a hello.py file", WORKSPACE)
        assert wf._state.turn_number == 2
        assert wf._state.claude_session_id == "session-new"

    @pytest.mark.asyncio
    async def test_event_before_workspace_is_ready_waits_instead_of_raising(self, side_effects):
        from project.workflow import StateModel

        wf = _workflow()
        wf._state = None
        wf._workspace_path = None

        async def _wait_until_on_task_create_finishes(condition, **_kw):
            assert not condition()
            wf._state = StateModel(claude_session_id=None, turn_number=0)
            assert not condition()  # state is set before the workspace activity returns
            wf._workspace_path = WORKSPACE
            assert condition()

        with patch("project.workflow.workflow.wait_condition", new=_wait_until_on_task_create_finishes):
            await wf.on_task_event_send(_event_params(TextContent(author="user", content="first message")))

        assert wf._state.turn_number == 1
        side_effects.create.assert_awaited_once()
        prompt, workspace, *_ = side_effects.execute_activity.await_args.kwargs["args"]
        assert (prompt, workspace) == ("first message", WORKSPACE)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
