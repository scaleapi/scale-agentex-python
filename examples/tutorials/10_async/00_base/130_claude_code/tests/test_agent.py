"""Tests for the async Claude Code tutorial agent.

LIVE tests (``TestClaudeCodeLive``):
  - Require the ``claude`` CLI on PATH and ``ANTHROPIC_API_KEY`` set.
  - Run the full agent end-to-end against a live Agentex server.
  - Skipped automatically when ``CLAUDE_LIVE_TESTS`` is not set to ``1``.

OFFLINE unit tests (``TestClaudeCodeOffline``):
  - Inject a fake async iterator of pre-recorded stream-json lines.
  - Assert the ``ClaudeCodeTurn`` + ``UnifiedEmitter`` pipeline drives
    ``auto_send_turn``, populates usage, and satisfies the ``HarnessTurn``
    protocol.
  - Always run -- no CLI or API key needed.
"""

from __future__ import annotations

import os
import json
from typing import AsyncIterator

import pytest

from agentex.types.task_message import TaskMessage

# ---------------------------------------------------------------------------
# Recorded stream-json fixtures
# ---------------------------------------------------------------------------

_TEXT_ONLY_LINES: list[str] = [
    json.dumps({"type": "system", "subtype": "init", "session_id": "sess-offline-async-1"}),
    json.dumps(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "Hello from async Claude Code!"}]},
        }
    ),
    json.dumps(
        {
            "type": "result",
            "usage": {"input_tokens": 12, "output_tokens": 6},
            "cost_usd": 0.0001,
            "duration_ms": 300,
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
        self.task_message = TaskMessage(id="msg-1", task_id="task-offline", content=initial_content)

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
    """Unit tests that run without a real claude CLI or network."""

    @pytest.mark.asyncio
    async def test_auto_send_text_only_opens_and_closes_context(self):
        """auto_send_turn opens and closes exactly one streaming context."""
        from agentex.lib.adk import ClaudeCodeTurn
        from agentex.lib.core.harness import UnifiedEmitter

        fake_streaming = _FakeStreaming()
        turn = ClaudeCodeTurn(_fake_lines(_TEXT_ONLY_LINES))
        emitter = UnifiedEmitter(
            task_id="offline-task",
            trace_id=None,
            parent_span_id=None,
            tracer=False,
            streaming=fake_streaming,
        )
        result = await emitter.auto_send_turn(turn)

        opened = [s for s in fake_streaming.sink if s[0] == "open"]
        closed = [s for s in fake_streaming.sink if s[0] == "close"]
        assert len(opened) == 1
        assert len(closed) == 1
        assert opened[0][1] == "text"

    @pytest.mark.asyncio
    async def test_auto_send_populates_final_text(self):
        """auto_send_turn result carries the agent's reply text."""
        from agentex.lib.adk import ClaudeCodeTurn
        from agentex.lib.core.harness import UnifiedEmitter

        fake_streaming = _FakeStreaming()
        turn = ClaudeCodeTurn(_fake_lines(_TEXT_ONLY_LINES))
        emitter = UnifiedEmitter(
            task_id="offline-task",
            trace_id=None,
            parent_span_id=None,
            tracer=False,
            streaming=fake_streaming,
        )
        result = await emitter.auto_send_turn(turn)
        assert "Hello from async Claude Code" in result.final_text

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
        assert usage.input_tokens == 12
        assert usage.output_tokens == 6
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


# ---------------------------------------------------------------------------
# Live tests (skipped unless CLAUDE_LIVE_TESTS=1)
# ---------------------------------------------------------------------------

pytestmark_live = pytest.mark.skipif(
    not os.environ.get("CLAUDE_LIVE_TESTS"),
    reason="Set CLAUDE_LIVE_TESTS=1 and ensure the `claude` CLI + ANTHROPIC_API_KEY are available",
)

AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "ab130-claude-code")


@pytestmark_live
class TestClaudeCodeLive:
    """Live async tests -- needs the claude CLI + ANTHROPIC_API_KEY."""

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

        from agentex.types import TextContentParam
        from agentex.types.agent_rpc_params import ParamsSendEventRequest

        task = client.tasks.create(agent_id=agent_id)
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

        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            msgs = client.messages.list(task_id=task_id)
            agent_msgs = [m for m in msgs if getattr(m.content, "author", None) == "agent"]
            if agent_msgs:
                assert len(agent_msgs) >= 1
                return
            time.sleep(2)

        raise AssertionError("No agent response received within 60 s")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
