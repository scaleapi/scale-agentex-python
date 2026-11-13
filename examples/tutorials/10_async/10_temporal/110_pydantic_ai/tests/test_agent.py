"""Live tests for the Temporal Pydantic AI agent.

These tests require a running agent (Temporal + Redis + ACP server + worker) and
exercise the unified-surface event_stream_handler end-to-end over the wire.

Offline coverage of the same wiring (TestModel + fake streaming/tracing) lives
in the SDK repo under ``tests/lib/core/harness/`` (the pydantic-ai temporal suite).

The offline tests at the end of this file (``TestSignalHandlerOffline``) call the
workflow's signal handler directly, with its collaborators patched, and need no
running agent: a user text event runs a turn, and an event the handler cannot
process (no content, or content that is not text) is ignored without raising
and without side effects.

To run these tests:
1. Make sure the agent is running (worker + ACP server)
2. Set AGENTEX_API_BASE_URL if not using the default
3. Run: pytest tests/test_agent.py -v
"""

import os
import uuid
from types import SimpleNamespace
from typing import Any
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from test_utils.async_utils import poll_messages, send_event_and_poll_yielding

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

AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at110-pydantic-ai")


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


# ---------------------------------------------------------------------------
# Offline signal-handler tests (no running agent, Temporal or API key needed)
# ---------------------------------------------------------------------------

TASK_ID = "task-offline"

# Event content a caller can send that the handler cannot process: Event.content
# is optional, and only TextContent carries a ``content: str``.
NON_TEXT_CONTENTS = [
    pytest.param(None, id="no-content"),
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


def _send_event_params(content: Any) -> SendEventParams:
    """Real ``SendEventParams``, as the ACP delivers an ``event/send`` to the workflow signal."""
    now = datetime.now(timezone.utc)
    return SendEventParams(
        agent=Agent(id="agent-1", acp_type="async", name=AGENT_NAME, description="", created_at=now, updated_at=now),
        task=Task(id=TASK_ID),
        event=Event(id="event-1", agent_id="agent-1", task_id=TASK_ID, sequence_id=1, content=content),
    )


class _FakeSpan:
    id = "span-1"
    output: Any = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass


@pytest.fixture
def workflow_module():
    """``project.workflow``; conftest.py sets the env vars it reads at import time."""
    import project.workflow

    return project.workflow


@pytest.fixture
def mocks(workflow_module, monkeypatch):
    """Patch what the signal handler calls, so it runs without Temporal, a model or a server."""
    run_result = SimpleNamespace(output="It is 72°F.", all_messages=lambda: ["model-request", "model-response"])
    m = SimpleNamespace(
        create=AsyncMock(),
        span=MagicMock(return_value=_FakeSpan()),
        agent=SimpleNamespace(run=AsyncMock(return_value=run_result)),
    )
    monkeypatch.setattr(workflow_module.adk.messages, "create", m.create)
    monkeypatch.setattr(workflow_module.adk.tracing, "span", m.span)
    monkeypatch.setattr(workflow_module, "temporal_agent", m.agent)
    return m


def _new_workflow(workflow_module):
    """A workflow instance with the attributes ``__init__`` sets, built without a Temporal runtime."""
    wf = workflow_module.HarnessPydanticAiWorkflow.__new__(workflow_module.HarnessPydanticAiWorkflow)
    wf.display_name = AGENT_NAME
    wf._complete_task = False
    wf._turn_number = 0
    wf._message_history = []
    return wf


class TestSignalHandlerOffline:
    """The signal handler, called directly with real event payloads."""

    @pytest.mark.asyncio
    async def test_user_text_event_runs_agent(self, workflow_module, mocks):
        """A user text event is echoed and run through the agent; the history is carried forward."""
        wf = _new_workflow(workflow_module)
        content = TextContent(author="user", content="What is the weather in Paris?")

        await wf.on_task_event_send(_send_event_params(content))

        mocks.create.assert_awaited_once_with(task_id=TASK_ID, content=content)
        mocks.agent.run.assert_awaited_once()
        assert mocks.agent.run.await_args.args == ("What is the weather in Paris?",)
        deps = mocks.agent.run.await_args.kwargs["deps"]
        assert (deps.task_id, deps.parent_span_id) == (TASK_ID, "span-1")
        assert wf._turn_number == 1
        assert wf._message_history == ["model-request", "model-response"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("content", NON_TEXT_CONTENTS)
    async def test_non_text_event_is_ignored(self, workflow_module, mocks, content):
        """An event the handler cannot process is ignored: no exception, no side effects.

        An exception raised by a signal handler fails the workflow task, and
        Temporal retries it forever by replaying the same signal from history, so
        the task's workflow would never process another event.
        """
        wf = _new_workflow(workflow_module)

        await wf.on_task_event_send(_send_event_params(content))

        mocks.create.assert_not_awaited()
        mocks.span.assert_not_called()
        mocks.agent.run.assert_not_awaited()
        assert wf._turn_number == 0
        assert wf._message_history == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
