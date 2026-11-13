"""Offline tests for the Gemini + LiteLLM Temporal tutorial's signal handler.

These tests do NOT require Temporal, a running Agentex server, or a Gemini API
key. They call ``on_task_event_send`` directly with real event payloads, with
its collaborators (``adk.messages``, tracing, ``Runner`` and
``workflow.wait_condition``) patched, and check that:

- a user text event is echoed, run through the agent, and the reply sent;
- an event that arrives before ``on_task_create`` has initialised the state
  waits for it instead of being dropped;
- an event the handler cannot process (no content, or content that is not
  text) is ignored without raising and without side effects.

To run: ``pytest tests/test_agent.py -v``
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.lib.types.acp import SendEventParams
from agentex.types.data_content import DataContent
from agentex.types.text_content import TextContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent

AGENT_NAME = os.environ.get("AGENT_NAME", "at100-gemini-litellm")
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


class _NoSpan:
    """What ``adk.tracing.span`` yields when the span could not be started."""

    async def __aenter__(self):
        return None

    async def __aexit__(self, *_a):
        pass


@pytest.fixture
def workflow_module():
    """``project.workflow``; conftest.py sets the env vars it reads at import time."""
    import project.workflow

    return project.workflow


@pytest.fixture
def mocks(workflow_module, monkeypatch):
    """Patch what the signal handler calls, so it runs without Temporal, a model or a server."""
    m = SimpleNamespace(
        wait_condition=AsyncMock(),
        create=AsyncMock(),
        span=MagicMock(return_value=_FakeSpan()),
        runner=SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(final_output="Hi, I'm Gemini."))),
    )
    monkeypatch.setattr(workflow_module.workflow, "wait_condition", m.wait_condition)
    monkeypatch.setattr(workflow_module.adk.messages, "create", m.create)
    monkeypatch.setattr(workflow_module.adk.tracing, "span", m.span)
    monkeypatch.setattr(workflow_module, "Runner", m.runner)
    return m


def _new_workflow(workflow_module, *, initialised: bool = True):
    """A workflow instance with the attributes ``__init__`` sets, built without a Temporal runtime.

    ``initialised`` stands in for ``on_task_create`` having already set up the conversation state.
    """
    wf = workflow_module.At100GeminiLitellmWorkflow.__new__(workflow_module.At100GeminiLitellmWorkflow)
    wf.display_name = AGENT_NAME
    wf._complete_task = False
    wf._state = workflow_module.StateModel(input_list=[], turn_number=0) if initialised else None
    wf._task_id = None
    wf._trace_id = None
    wf._parent_span_id = None
    return wf


class TestSignalHandlerOffline:
    """The signal handler, called directly with real event payloads."""

    @pytest.mark.asyncio
    async def test_user_text_event_runs_agent_and_replies(self, workflow_module, mocks):
        """A user text event is echoed, added to the history, run through the agent, and answered."""
        wf = _new_workflow(workflow_module)
        content = TextContent(author="user", content="Hello")

        await wf.on_task_event_send(_send_event_params(content))

        assert mocks.create.await_args_list == [
            call(task_id=TASK_ID, content=content),
            call(task_id=TASK_ID, content=TextContent(author="agent", content="Hi, I'm Gemini.")),
        ]
        mocks.runner.run.assert_awaited_once()
        assert mocks.runner.run.await_args.args[1] == [{"role": "user", "content": "Hello"}]
        assert wf._state.turn_number == 1
        assert wf._task_id == TASK_ID

    @pytest.mark.asyncio
    async def test_user_text_event_runs_when_tracing_yields_no_span(self, workflow_module, mocks):
        """Tracing is best effort: when the span can't be started the turn still runs and replies."""
        mocks.span.return_value = _NoSpan()
        wf = _new_workflow(workflow_module)

        await wf.on_task_event_send(_send_event_params(TextContent(author="user", content="Hello")))

        mocks.runner.run.assert_awaited_once()
        assert mocks.create.await_count == 2
        assert wf._state.turn_number == 1

    @pytest.mark.asyncio
    async def test_event_before_state_is_initialised_waits_for_it(self, workflow_module, mocks, monkeypatch):
        """A signal delivered before ``on_task_create`` sets up the state is processed once it exists."""
        wf = _new_workflow(workflow_module, initialised=False)

        async def _wait_condition(predicate):
            # Temporal resumes the handler once on_task_create has initialised the state.
            assert not predicate()
            wf._state = workflow_module.StateModel(input_list=[], turn_number=0)
            assert predicate()

        monkeypatch.setattr(workflow_module.workflow, "wait_condition", _wait_condition)
        content = TextContent(author="user", content="Hello")

        await wf.on_task_event_send(_send_event_params(content))

        assert mocks.create.await_args_list[0] == call(task_id=TASK_ID, content=content)
        mocks.runner.run.assert_awaited_once()
        assert wf._state.turn_number == 1
        assert wf._state.input_list == [{"role": "user", "content": "Hello"}]

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

        mocks.wait_condition.assert_not_awaited()
        mocks.create.assert_not_awaited()
        mocks.span.assert_not_called()
        mocks.runner.run.assert_not_awaited()
        assert wf._state == workflow_module.StateModel(input_list=[], turn_number=0)
        assert wf._task_id is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
