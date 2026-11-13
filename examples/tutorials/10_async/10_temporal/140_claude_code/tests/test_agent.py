"""Tests for the Temporal Claude Code tutorial agent.

LIVE tests (``TestClaudeCodeLive``):
  - Require Temporal server, the ACP server, the Temporal worker, the ``claude``
    CLI on PATH, and ``ANTHROPIC_API_KEY`` set.
  - Run the full agent end-to-end against a live Agentex server.
  - Skipped automatically when ``CLAUDE_LIVE_TESTS`` is not set to ``1``.

OFFLINE unit tests (``TestClaudeCodeOffline``, ``TestClaudeCodeWorkflowOffline``):
  - Inject a fake async iterator of pre-recorded stream-json lines.
  - Assert the ``ClaudeCodeTurn`` + ``UnifiedEmitter`` pipeline drives
    ``auto_send_turn``, populates usage, and satisfies the ``HarnessTurn``
    protocol.
  - Call the workflow's signal handler directly (collaborators patched) and
    assert it runs a turn for a user text event, and ignores events it cannot
    process (no content, or content that is not text) without raising and
    without side effects.
  - Always run -- no CLI or API key needed.
"""

from __future__ import annotations

import os
import json
from types import SimpleNamespace
from typing import Any, AsyncIterator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.protocol.acp import SendEventParams
from agentex.types.data_content import DataContent
from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent

# ---------------------------------------------------------------------------
# Recorded stream-json fixtures
# ---------------------------------------------------------------------------

_TEXT_ONLY_LINES: list[str] = [
    json.dumps({"type": "system", "subtype": "init", "session_id": "sess-temporal-offline-1"}),
    json.dumps(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "Hello from Temporal Claude Code!"}]},
        }
    ),
    json.dumps(
        {
            "type": "result",
            "session_id": "sess-temporal-offline-1",
            "usage": {"input_tokens": 15, "output_tokens": 7},
            "cost_usd": 0.00015,
            "duration_ms": 350,
            "num_turns": 1,
        }
    ),
]


async def _fake_lines(lines: list[str]) -> AsyncIterator[str]:
    """Async iterator of pre-recorded stream-json lines (no subprocess)."""
    for line in lines:
        yield line


# ---------------------------------------------------------------------------
# Fake streaming backend
# ---------------------------------------------------------------------------


class _FakeCtx:
    def __init__(self, sink, content_type, initial_content):
        self.sink = sink
        self.content_type = content_type
        self.task_message = TaskMessage(id="msg-t1", task_id="task-temporal-offline", content=initial_content)

    async def __aenter__(self):
        self.sink.append(("open", self.content_type))
        return self

    async def __aexit__(self, *a):
        await self.close()
        return False

    async def close(self):
        self.sink.append(("close", self.content_type))

    async def stream_update(self, update):
        self.sink.append(("update", update))
        return update


class _FakeStreaming:
    def __init__(self):
        self.sink: list = []

    def streaming_task_message_context(self, task_id, initial_content, streaming_mode="coalesced", created_at=None):  # noqa: ARG002
        ctype = getattr(initial_content, "type", None)
        self.sink.append(("ctx", ctype))
        return _FakeCtx(self.sink, ctype, initial_content)


# ---------------------------------------------------------------------------
# Offline tests (always run -- no CLI or API key needed)
# ---------------------------------------------------------------------------


class TestClaudeCodeOffline:
    """Unit tests that run without a real claude CLI, Temporal, or network."""

    @pytest.mark.asyncio
    async def test_auto_send_text_only_produces_output(self):
        """auto_send_turn result carries the agent's reply text."""
        from agentex.lib.adk import ClaudeCodeTurn
        from agentex.lib.core.harness import UnifiedEmitter

        fake_streaming = _FakeStreaming()
        turn = ClaudeCodeTurn(_fake_lines(_TEXT_ONLY_LINES))
        emitter = UnifiedEmitter(
            task_id="offline-temporal",
            trace_id=None,
            parent_span_id=None,
            tracer=False,
            streaming=fake_streaming,
        )
        result = await emitter.auto_send_turn(turn)
        assert "Hello from Temporal Claude Code" in result.final_text

    @pytest.mark.asyncio
    async def test_usage_populated_after_stream_exhausted(self):
        """Usage is populated after the events stream is exhausted."""
        from agentex.lib.adk import ClaudeCodeTurn
        from agentex.lib.core.harness import UnifiedEmitter

        fake_streaming = _FakeStreaming()
        turn = ClaudeCodeTurn(_fake_lines(_TEXT_ONLY_LINES))
        emitter = UnifiedEmitter(
            task_id="t",
            trace_id=None,
            parent_span_id=None,
            tracer=False,
            streaming=fake_streaming,
        )
        await emitter.auto_send_turn(turn)
        usage = turn.usage()
        assert usage.input_tokens == 15
        assert usage.output_tokens == 7
        assert usage.num_llm_calls == 1

    @pytest.mark.asyncio
    async def test_stream_task_message_done_present(self):
        """StreamTaskMessageDone must appear via yield_turn on a ClaudeCodeTurn."""
        from agentex.lib.adk import ClaudeCodeTurn
        from agentex.lib.core.harness import UnifiedEmitter
        from agentex.types.task_message_update import StreamTaskMessageDone

        turn = ClaudeCodeTurn(_fake_lines(_TEXT_ONLY_LINES))
        emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None)
        events = [e async for e in emitter.yield_turn(turn)]
        assert any(isinstance(e, StreamTaskMessageDone) for e in events), (
            "Expected at least one StreamTaskMessageDone event"
        )

    @pytest.mark.asyncio
    async def test_session_id_captured_in_result_envelope(self):
        """The result envelope carries session_id (multi-turn resume support)."""
        from agentex.lib.adk import ClaudeCodeTurn
        from agentex.lib.core.harness import UnifiedEmitter

        fake_streaming = _FakeStreaming()
        turn = ClaudeCodeTurn(_fake_lines(_TEXT_ONLY_LINES))
        emitter = UnifiedEmitter(
            task_id="t",
            trace_id=None,
            parent_span_id=None,
            tracer=False,
            streaming=fake_streaming,
        )
        await emitter.auto_send_turn(turn)
        assert turn._result_envelope is not None
        assert turn._result_envelope.get("session_id") == "sess-temporal-offline-1"


# ---------------------------------------------------------------------------
# Offline signal-handler tests (always run -- no Temporal, CLI or API key needed)
# ---------------------------------------------------------------------------

TASK_ID = "task-temporal-offline"

# Event content a caller can send that the handler cannot process: Event.content
# is optional, and only TextContent carries a ``content: str``.
NON_TEXT_CONTENTS = [
    pytest.param(None, id="no-content"),
    pytest.param(DataContent(author="user", data={}), id="data"),
    pytest.param(ReasoningContent(author="user", summary=["thinking"], type="reasoning"), id="reasoning"),
    pytest.param(
        ToolRequestContent(author="user", name="Bash", tool_call_id="call-1", arguments={"command": "ls"}),
        id="tool-request",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="Bash", tool_call_id="call-1", content={"k": "v"}),
        id="tool-response-dict",
    ),
    pytest.param(
        ToolResponseContent(author="user", name="Bash", tool_call_id="call-1", content=[1, 2]),
        id="tool-response-list",
    ),
]


def _send_event_params(content: Any) -> SendEventParams:
    """Real ``SendEventParams``, as the ACP delivers an ``event/send`` to the workflow signal."""
    now = datetime.now(timezone.utc)
    return SendEventParams(
        agent=Agent(
            id="agent-1", acp_type="async", name="at140-claude-code", description="", created_at=now, updated_at=now
        ),
        task=Task(id=TASK_ID),
        event=Event(id="event-1", agent_id="agent-1", task_id=TASK_ID, sequence_id=1, content=content),
    )


class _FakeSpan:
    id = "span-temporal-offline"
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
    """Patch what the signal handler calls, so it runs without Temporal, the CLI or a server."""
    m = SimpleNamespace(
        create=AsyncMock(),
        span=MagicMock(return_value=_FakeSpan()),
        execute_activity=AsyncMock(return_value={"final_text": "hello from claude", "session_id": "sess-1"}),
    )
    monkeypatch.setattr(workflow_module.adk.messages, "create", m.create)
    monkeypatch.setattr(workflow_module.adk.tracing, "span", m.span)
    monkeypatch.setattr(workflow_module.workflow, "execute_activity", m.execute_activity)
    monkeypatch.setattr(workflow_module.workflow, "now", lambda: None)
    return m


def _new_workflow(workflow_module):
    """A workflow instance with the attributes ``__init__`` sets, built without a Temporal runtime."""
    wf = workflow_module.At140ClaudeCodeWorkflow.__new__(workflow_module.At140ClaudeCodeWorkflow)
    wf.display_name = "at140-claude-code"
    wf._complete_task = False
    wf._turn_number = 0
    wf._session_id = None
    return wf


class TestClaudeCodeWorkflowOffline:
    """The signal handler, called directly with real event payloads."""

    @pytest.mark.asyncio
    async def test_user_text_event_runs_turn(self, workflow_module, mocks):
        """A user text event is echoed, run through the activity, and its session_id kept."""
        wf = _new_workflow(workflow_module)
        content = TextContent(author="user", content="say hello")

        await wf.on_task_event_send(_send_event_params(content))

        mocks.create.assert_awaited_once_with(task_id=TASK_ID, content=content)
        mocks.execute_activity.assert_awaited_once()
        activity_params = mocks.execute_activity.await_args.args[1]
        assert activity_params.prompt == "say hello"
        assert activity_params.session_id is None
        assert wf._turn_number == 1
        assert wf._session_id == "sess-1"

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
        mocks.execute_activity.assert_not_awaited()
        assert wf._turn_number == 0
        assert wf._session_id is None


# ---------------------------------------------------------------------------
# Live tests (skipped unless CLAUDE_LIVE_TESTS=1)
# ---------------------------------------------------------------------------

pytestmark_live = pytest.mark.skipif(
    not os.environ.get("CLAUDE_LIVE_TESTS"),
    reason="Set CLAUDE_LIVE_TESTS=1 and ensure the `claude` CLI + ANTHROPIC_API_KEY are available",
)

AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at140-claude-code")


@pytestmark_live
class TestClaudeCodeLive:
    """Live Temporal tests -- needs Temporal server + the claude CLI + ANTHROPIC_API_KEY."""

    @pytest.fixture
    def client(self):
        from agentex import Agentex

        return Agentex(base_url=AGENTEX_API_BASE_URL)

    @pytest.fixture
    def agent_name(self):
        return AGENT_NAME

    @pytest.fixture
    def agent_id(self, client, agent_name):
        agents = client.agents.list()
        for agent in agents:
            if agent.name == agent_name:
                return agent.id
        raise ValueError(f"Agent {agent_name!r} not found.")

    def test_send_simple_message(self, client, agent_id: str):
        """Create a task, send a message, and poll until a response appears."""
        import time
        import uuid

        from agentex.types import TextContentParam
        from agentex.types.agent_rpc_params import ParamsSendEventRequest, ParamsCreateTaskRequest

        task = client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex)).result
        assert task is not None
        task_id = task.id

        client.agents.send_event(
            agent_id=agent_id,
            params=ParamsSendEventRequest(
                task_id=task_id,
                content=TextContentParam(
                    author="user",
                    content="Reply with exactly three words: hello from claude",
                    type="text",
                ),
            ),
        )

        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            msgs = client.messages.list(task_id=task_id)
            agent_msgs = [m for m in msgs if getattr(m.content, "author", None) == "agent"]
            response_msgs = [m for m in agent_msgs if "Task initialized" not in str(getattr(m.content, "content", ""))]
            if response_msgs:
                assert len(response_msgs) >= 1
                return
            time.sleep(3)

        raise AssertionError("No agent response received within 90 s")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
