"""Offline unit tests for the Temporal Claude Code tutorial agent.

These tests do NOT require the ``claude`` CLI, Temporal, or ANTHROPIC_API_KEY.
They inject a fake async iterator of pre-recorded stream-json lines in place of
the real subprocess spawn and a fake streaming backend, then assert that the
workflow's turn logic correctly drives ``UnifiedEmitter.auto_send_turn``.

The injection seam is the ``_spawn_claude`` function in ``project/workflow.py``.
Tests monkeypatch it with a coroutine returning a pre-recorded async iterator.
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
    json.dumps({"type": "system", "subtype": "init", "session_id": "sess-temporal-1"}),
    json.dumps(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "Hello from Temporal Claude Code!"}]},
        }
    ),
    json.dumps(
        {
            "type": "result",
            "session_id": "sess-temporal-1",
            "usage": {"input_tokens": 15, "output_tokens": 7},
            "cost_usd": 0.00015,
            "duration_ms": 350,
            "num_turns": 1,
        }
    ),
]

_TOOL_CALL_LINES: list[str] = [
    json.dumps({"type": "system", "subtype": "init", "session_id": "sess-temporal-2"}),
    json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool_temporal",
                        "name": "Bash",
                        "input": {"command": "ls /tmp"},
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
                        "tool_use_id": "tool_temporal",
                        "content": "file1\nfile2\n",
                        "is_error": False,
                    }
                ]
            },
        }
    ),
    json.dumps(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "Listed files."}]},
        }
    ),
    json.dumps(
        {
            "type": "result",
            "session_id": "sess-temporal-2",
            "usage": {"input_tokens": 30, "output_tokens": 12},
            "cost_usd": 0.0004,
            "duration_ms": 600,
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
# Helpers
# ---------------------------------------------------------------------------


async def _fake_lines(lines: list[str]) -> AsyncIterator[str]:
    for line in lines:
        yield line


async def _run_turn(lines: list[str]):
    fake_streaming = _FakeStreaming()
    turn = ClaudeCodeTurn(_fake_lines(lines))
    emitter = UnifiedEmitter(
        task_id="offline-temporal",
        trace_id=None,
        parent_span_id=None,
        tracer=False,
        streaming=fake_streaming,
    )
    result = await emitter.auto_send_turn(turn)
    return result, fake_streaming.sink, turn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_only_produces_agent_output():
    result, sink, _ = await _run_turn(_TEXT_ONLY_LINES)
    assert "Hello from Temporal Claude Code" in result.final_text


@pytest.mark.asyncio
async def test_usage_from_result_envelope():
    """Usage is available from turn.usage() after the events are exhausted.

    UnifiedEmitter.auto_send_turn evaluates turn.usage() eagerly before the
    async generator is consumed, so result.usage is a pre-exhaust snapshot.
    Read usage directly from the turn after _run_turn completes instead.
    """
    result, _, turn = await _run_turn(_TEXT_ONLY_LINES)
    usage = turn.usage()
    assert usage.input_tokens == 15
    assert usage.output_tokens == 7
    assert usage.num_llm_calls == 1


@pytest.mark.asyncio
async def test_session_id_captured_in_result_envelope():
    """Verify the result envelope carries session_id (multi-turn resume support)."""
    _, _, turn = await _run_turn(_TEXT_ONLY_LINES)
    assert turn._result_envelope is not None
    assert turn._result_envelope.get("session_id") == "sess-temporal-1"


@pytest.mark.asyncio
async def test_tool_call_context_types():
    result, sink, _ = await _run_turn(_TOOL_CALL_LINES)
    opened = [s for s in sink if s[0] == "open"]
    content_types = [s[1] for s in opened]
    assert "tool_request" in content_types
    assert "text" in content_types


@pytest.mark.asyncio
async def test_spawn_seam_concept():
    """Demonstrate the injectable spawn seam pattern used in project/workflow.py.

    ``_spawn_claude(prompt, session_id=None)`` is a top-level async generator.
    A drop-in replacement (e.g. via monkeypatch) supplies pre-recorded lines
    and captures call arguments. The session_id parameter enables multi-turn
    resume (``claude -r <session_id>``).
    """
    called: list[tuple] = []

    async def _fake_spawn(prompt: str, session_id=None) -> AsyncIterator[str]:
        called.append((prompt, session_id))
        for line in _TEXT_ONLY_LINES:
            yield line

    fake_streaming = _FakeStreaming()
    turn = ClaudeCodeTurn(_fake_spawn("temporal prompt", session_id="old-sid"))
    emitter = UnifiedEmitter(
        task_id="t",
        trace_id=None,
        parent_span_id=None,
        tracer=False,
        streaming=fake_streaming,
    )
    result = await emitter.auto_send_turn(turn)

    assert called == [("temporal prompt", "old-sid")]
    assert "Hello from Temporal Claude Code" in result.final_text
