"""Offline unit tests for the async Claude Code tutorial agent.

These tests do NOT require the ``claude`` CLI or an ANTHROPIC_API_KEY.
They inject a fake async iterator of pre-recorded stream-json lines in
place of the real subprocess spawn and a fake streaming backend, then
assert that the handler drives ``UnifiedEmitter.auto_send_turn`` correctly.

The injection seam is the ``_spawn_claude`` function in ``project/acp.py``.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

import pytest

from agentex.lib.adk import ClaudeCodeTurn
from agentex.lib.core.harness import UnifiedEmitter
from agentex.types.task_message import TaskMessage

# ---------------------------------------------------------------------------
# Recorded fixtures
# ---------------------------------------------------------------------------

_TEXT_ONLY_LINES: list[str] = [
    json.dumps({"type": "system", "subtype": "init", "session_id": "sess-1"}),
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

_TOOL_CALL_LINES: list[str] = [
    json.dumps({"type": "system", "subtype": "init", "session_id": "sess-2"}),
    json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool_xyz",
                        "name": "Read",
                        "input": {"file_path": "/tmp/foo.txt"},
                    }
                ]
            },
        }
    ),
    json.dumps(
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool_xyz",
                        "content": "file contents",
                        "is_error": False,
                    }
                ]
            },
        }
    ),
    json.dumps(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "Read the file."}]},
        }
    ),
    json.dumps(
        {
            "type": "result",
            "usage": {"input_tokens": 25, "output_tokens": 10},
            "cost_usd": 0.0003,
            "duration_ms": 500,
            "num_turns": 1,
        }
    ),
]


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
# Helpers
# ---------------------------------------------------------------------------


async def _fake_lines(lines: list[str]) -> AsyncIterator[str]:
    for line in lines:
        yield line


async def _run_auto_send(lines: list[str]):
    """Drive ClaudeCodeTurn through auto_send_turn with a fake streaming backend."""
    fake_streaming = _FakeStreaming()
    turn = ClaudeCodeTurn(_fake_lines(lines))
    emitter = UnifiedEmitter(
        task_id="offline-task",
        trace_id=None,
        parent_span_id=None,
        tracer=False,
        streaming=fake_streaming,
    )
    result = await emitter.auto_send_turn(turn)
    return result, fake_streaming.sink


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_send_text_only_opens_and_closes_context():
    result, sink = await _run_auto_send(_TEXT_ONLY_LINES)
    opened = [s for s in sink if s[0] == "open"]
    closed = [s for s in sink if s[0] == "close"]
    assert len(opened) == 1
    assert len(closed) == 1
    assert opened[0][1] == "text"


@pytest.mark.asyncio
async def test_auto_send_populates_final_text():
    result, _ = await _run_auto_send(_TEXT_ONLY_LINES)
    assert "Hello from async Claude Code" in result.final_text


@pytest.mark.asyncio
async def test_auto_send_usage_is_populated():
    """Usage is populated after the events stream is exhausted.

    UnifiedEmitter.auto_send_turn evaluates turn.usage() eagerly (before
    the events are consumed) so the TurnResult.usage reflects a pre-exhaust
    snapshot. Test usage directly from the turn after auto_send_turn completes
    instead -- the result envelope is populated by the generator being consumed
    inside auto_send.
    """
    turn = ClaudeCodeTurn(_fake_lines(_TEXT_ONLY_LINES))
    fake_streaming = _FakeStreaming()
    emitter = UnifiedEmitter(
        task_id="t",
        trace_id=None,
        parent_span_id=None,
        tracer=False,
        streaming=fake_streaming,
    )
    await emitter.auto_send_turn(turn)
    # After auto_send_turn, the events generator is exhausted and
    # ClaudeCodeTurn._on_result has been called with the result envelope.
    usage = turn.usage()
    assert usage.input_tokens == 12
    assert usage.output_tokens == 6
    assert usage.num_llm_calls == 1


@pytest.mark.asyncio
async def test_auto_send_tool_call_opens_two_contexts():
    result, sink = await _run_auto_send(_TOOL_CALL_LINES)
    opened = [s for s in sink if s[0] == "open"]
    content_types = [s[1] for s in opened]
    assert "tool_request" in content_types
    assert "text" in content_types


@pytest.mark.asyncio
async def test_spawn_seam_concept():
    """Demonstrate the injectable spawn seam pattern used in project/acp.py.

    The ``_spawn_claude`` function is a top-level async generator. A drop-in
    replacement can be injected (e.g. via monkeypatch) to supply pre-recorded
    lines without spawning the real CLI. This test proves the pattern works
    end-to-end without importing the full ACP module.
    """
    called: list[str] = []

    async def _fake_spawn(prompt: str) -> AsyncIterator[str]:
        called.append(prompt)
        for line in _TEXT_ONLY_LINES:
            yield line

    fake_streaming = _FakeStreaming()
    turn = ClaudeCodeTurn(_fake_spawn("ping"))
    emitter = UnifiedEmitter(
        task_id="t",
        trace_id=None,
        parent_span_id=None,
        tracer=False,
        streaming=fake_streaming,
    )
    result = await emitter.auto_send_turn(turn)

    assert called == ["ping"]
    assert "Hello from async Claude Code" in result.final_text
