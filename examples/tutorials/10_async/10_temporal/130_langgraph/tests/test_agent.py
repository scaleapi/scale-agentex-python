"""Integration tests for the Temporal harness LangGraph agent (live agent required).

These drive a *running* agent over the AgentEx API and verify that:
- the agent sends a welcome message on task creation,
- a weather question triggers a tool_request / tool_response round-trip
  (proving the LLM node ran as a Temporal activity and the tool node ran),
- the final answer reflects the tool output.

The offline tests at the end of this file (``TestSignalHandlerOffline``) call the
workflow's signal handler directly, with its collaborators patched, and need no
running agent: a user text event runs the graph, and an event the handler cannot
process (no content, or content that is not text) is ignored without raising
and without side effects.

To run:
1. Start the agent (worker + ACP server): ``agentex agents run --manifest manifest.yaml``
2. Set AGENTEX_API_BASE_URL if not using the default
3. ``pytest tests/test_agent.py -v``
"""

import os
import uuid
from types import SimpleNamespace
from typing import Any
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

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
        task_response = await client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex))
        task = task_response.result
        assert task is not None

        task_creation_found = False
        async for message in poll_messages(client=client, task_id=task.id, timeout=30, sleep_interval=1.0):
            assert isinstance(message, TaskMessage)
            if message.content and message.content.type == "text" and message.content.author == "agent":
                task_creation_found = True
                break
        assert task_creation_found, "Task creation welcome message not found"

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

            if message.content and message.content.type == "text" and message.content.author == "agent":
                final_message = message
                content_length = len(getattr(message.content, "content", "") or "")
                if getattr(message, "streaming_status", None) in (None, "DONE") and content_length > 0:
                    if seen_tool_response:
                        break

        assert seen_tool_request, "Expected a tool_request (agent calling get_weather)"
        assert seen_tool_response, "Expected a tool_response (get_weather result)"
        assert final_message is not None, "Expected a final agent text message"
        final_text = getattr(final_message.content, "content", None) if final_message.content else None
        assert isinstance(final_text, str) and len(final_text) > 0
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


@pytest.fixture
def workflow_module():
    """``project.workflow``; conftest.py sets the env vars it reads at import time."""
    import project.workflow

    return project.workflow


@pytest.fixture
def mocks(workflow_module, monkeypatch):
    """Patch what the signal handler calls, so it runs without Temporal, a model or a server."""

    async def _ainvoke(state):
        return {"messages": [*state["messages"], {"role": "assistant", "content": "It is 72°F."}]}

    graph = MagicMock()
    graph.compile.return_value.ainvoke = AsyncMock(side_effect=_ainvoke)
    m = SimpleNamespace(create=AsyncMock(), lg_graph=MagicMock(return_value=graph), emit=AsyncMock())
    monkeypatch.setattr(workflow_module.adk.messages, "create", m.create)
    monkeypatch.setattr(workflow_module, "lg_graph", m.lg_graph)
    monkeypatch.setattr(workflow_module, "emit_langgraph_messages", m.emit)
    return m


def _new_workflow(workflow_module):
    """A workflow instance with the attributes ``__init__`` sets, built without a Temporal runtime."""
    wf = workflow_module.AtHarnessLanggraphWorkflow.__new__(workflow_module.AtHarnessLanggraphWorkflow)
    wf.display_name = AGENT_NAME
    wf._complete_task = False
    wf._messages = []
    wf._emitted = 0
    return wf


class TestSignalHandlerOffline:
    """The signal handler, called directly with real event payloads."""

    @pytest.mark.asyncio
    async def test_user_text_event_runs_graph(self, workflow_module, mocks):
        """A user text event is echoed, run through the graph, and the new messages surfaced."""
        wf = _new_workflow(workflow_module)
        content = TextContent(author="user", content="What is the weather in Paris?")

        await wf.on_task_event_send(_send_event_params(content))

        mocks.create.assert_awaited_once_with(task_id=TASK_ID, content=content)
        mocks.lg_graph.assert_called_once_with(workflow_module.GRAPH_NAME)
        assert wf._messages == [
            {"role": "user", "content": "What is the weather in Paris?"},
            {"role": "assistant", "content": "It is 72°F."},
        ]
        mocks.emit.assert_awaited_once_with(wf._messages, TASK_ID)
        assert wf._emitted == 2

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
        mocks.lg_graph.assert_not_called()
        mocks.emit.assert_not_awaited()
        assert wf._messages == []
        assert wf._emitted == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
