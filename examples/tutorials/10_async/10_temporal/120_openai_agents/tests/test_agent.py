"""Offline tests for the Temporal OpenAI Agents harness tutorial.

These tests do NOT require a running Agentex server, Temporal, Redis, or an
OpenAI API key. They verify the delivery path the harness activity uses: an
``OpenAITurn`` built from an injected canonical stream, pushed through
``UnifiedEmitter.auto_send_turn`` with an injected fake streaming backend,
returns the accumulated final text (which the activity returns to the workflow).

They also call the workflow's signal handler directly (collaborators patched):
a user text event runs a turn through the harness activity, and an event the
handler cannot process (no content, or content that is not text) is ignored
without raising and without side effects.

To run: ``pytest tests/test_agent.py -v``
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.lib.types.acp import SendEventParams
from agentex.types.data_content import DataContent
from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk.providers._modules.openai_turn import OpenAITurn


class _FakeCtx:
    def __init__(self, initial_content):
        self.task_message = TaskMessage(id="m-1", task_id="task-1", content=initial_content)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        await self.close()
        return False

    async def close(self):
        pass

    async def stream_update(self, update):
        return update


class _FakeStreaming:
    def streaming_task_message_context(self, task_id, initial_content, **_kwargs):  # noqa: ARG002
        return _FakeCtx(initial_content)


async def _canonical_stream(events):
    for e in events:
        yield e


@pytest.mark.asyncio
async def test_activity_delivery_returns_final_text():
    events = [
        StreamTaskMessageStart(type="start", index=0, content=TextContent(type="text", author="agent", content="")),
        StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="72")),
        StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="F")),
        StreamTaskMessageDone(type="done", index=0),
    ]
    turn = OpenAITurn(stream=_canonical_stream(events), model="gpt-4o")
    emitter = UnifiedEmitter(
        task_id="task-1",
        trace_id=None,
        parent_span_id=None,
        streaming=_FakeStreaming(),
    )

    result = await emitter.auto_send_turn(turn)
    assert result.final_text == "72F"


# ---------------------------------------------------------------------------
# Signal handler (no Temporal, Redis or API key needed)
# ---------------------------------------------------------------------------

TASK_ID = "task-1"

# Event content a caller can send that the handler cannot process: Event.content
# is optional, and only TextContent carries a ``content: str``.
NON_TEXT_CONTENTS = [
    pytest.param(None, id="no-content"),
    pytest.param(DataContent(author="user", data={}), id="data"),
    pytest.param(ReasoningContent(author="user", summary=["thinking"], type="reasoning"), id="reasoning"),
    pytest.param(
        ToolRequestContent(author="user", name="weather", tool_call_id="call-1", arguments={"city": "Paris"}),
        id="tool-request",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="weather", tool_call_id="call-1", content={"k": "v"}),
        id="tool-response-dict",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="weather", tool_call_id="call-1", content=[1, 2]),
        id="tool-response-list",
    ),
]


def _send_event_params(content: Any) -> SendEventParams:
    """Real ``SendEventParams``, as the ACP delivers an ``event/send`` to the workflow signal."""
    now = datetime.now(timezone.utc)
    return SendEventParams(
        agent=Agent(
            id="agent-1", acp_type="async", name="at120-openai-agents", description="", created_at=now, updated_at=now
        ),
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
    turn_result = workflow_module.RunHarnessAgentResult(
        final_text="72F",
        input_list=[
            {"role": "user", "content": "What is the weather in Paris?"},
            {"role": "assistant", "content": "72F"},
        ],
    )
    m = SimpleNamespace(
        create=AsyncMock(),
        span=MagicMock(return_value=_FakeSpan()),
        execute_activity=AsyncMock(return_value=turn_result),
    )
    monkeypatch.setattr(workflow_module.adk.messages, "create", m.create)
    monkeypatch.setattr(workflow_module.adk.tracing, "span", m.span)
    monkeypatch.setattr(workflow_module.workflow, "execute_activity", m.execute_activity)
    monkeypatch.setattr(workflow_module.workflow, "now", lambda: None)
    return m


def _new_workflow(workflow_module):
    """A workflow instance with the attributes ``__init__`` sets, built without a Temporal runtime."""
    wf = workflow_module.At140HarnessOpenaiWorkflow.__new__(workflow_module.At140HarnessOpenaiWorkflow)
    wf.display_name = "at120-openai-agents"
    wf._complete_task = False
    wf._turn_number = 0
    wf._messages = []
    return wf


@pytest.mark.asyncio
async def test_user_text_event_runs_harness_activity(workflow_module, mocks):
    """A user text event is echoed and run through the harness activity; the history is carried forward."""
    wf = _new_workflow(workflow_module)
    content = TextContent(author="user", content="What is the weather in Paris?")

    await wf.on_task_event_send(_send_event_params(content))

    mocks.create.assert_awaited_once_with(task_id=TASK_ID, content=content)
    mocks.execute_activity.assert_awaited_once()
    activity_params = mocks.execute_activity.await_args.args[1]
    assert activity_params.user_message == "What is the weather in Paris?"
    assert activity_params.input_list == []
    assert wf._turn_number == 1
    assert wf._messages == mocks.execute_activity.return_value.input_list


@pytest.mark.asyncio
@pytest.mark.parametrize("content", NON_TEXT_CONTENTS)
async def test_non_text_event_is_ignored(workflow_module, mocks, content):
    """An event the handler cannot process is ignored: no exception, no side effects.

    An exception raised by a signal handler fails the workflow task, and
    Temporal retries it forever by replaying the same signal from history, so
    the task's workflow would never process another event.
    """
    wf = _new_workflow(workflow_module)

    await wf.on_task_event_send(_send_event_params(content))

    mocks.create.assert_not_awaited()
    mocks.span.assert_not_called()
    mocks.execute_activity.assert_not_awaited()
    assert wf._turn_number == 0
    assert wf._messages == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
