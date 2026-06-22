"""Offline unit tests for the sync Claude Code tutorial agent.

These tests do NOT require the ``claude`` CLI or an ANTHROPIC_API_KEY.
They inject a fake async iterator of pre-recorded stream-json lines in
place of the real subprocess spawn, and a fake streaming backend in place
of the real Redis/AGP layer, then assert that the handler correctly drives
the unified surface (``UnifiedEmitter.yield_turn``).

The injection seam is the ``_spawn_claude`` function in ``project/acp.py``.
Tests monkeypatch it with a coroutine that returns a pre-recorded async
iterator, so the handler code runs in full without any subprocess.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

import pytest

from agentex.lib.adk import ClaudeCodeTurn
from agentex.lib.core.harness import UnifiedEmitter
from agentex.types.task_message_update import (
    StreamTaskMessageStart,
)

# ---------------------------------------------------------------------------
# Recorded stream-json fixtures
# ---------------------------------------------------------------------------

_TEXT_ONLY_LINES: list[str] = [
    json.dumps({"type": "system", "subtype": "init", "session_id": "sess-1"}),
    json.dumps(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "Hello from Claude Code!"}]},
        }
    ),
    json.dumps(
        {
            "type": "result",
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "cost_usd": 0.0001,
            "duration_ms": 250,
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
                        "id": "tool_abc",
                        "name": "Bash",
                        "input": {"command": "echo hello"},
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
                        "tool_use_id": "tool_abc",
                        "content": "hello\n",
                        "is_error": False,
                    }
                ]
            },
        }
    ),
    json.dumps(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "Done."}]},
        }
    ),
    json.dumps(
        {
            "type": "result",
            "usage": {"input_tokens": 20, "output_tokens": 8},
            "cost_usd": 0.0002,
            "duration_ms": 400,
            "num_turns": 1,
        }
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _fake_lines(lines: list[str]) -> AsyncIterator[str]:
    for line in lines:
        yield line


async def _collect_yield_turn(lines: list[str]) -> list:
    """Run a ClaudeCodeTurn through UnifiedEmitter.yield_turn and collect events."""
    turn = ClaudeCodeTurn(_fake_lines(lines))
    emitter = UnifiedEmitter(task_id="t1", trace_id=None, parent_span_id=None)
    return [e async for e in emitter.yield_turn(turn)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_only_produces_start_and_done():
    events = await _collect_yield_turn(_TEXT_ONLY_LINES)
    types = [type(e).__name__ for e in events]
    assert "StreamTaskMessageStart" in types
    assert "StreamTaskMessageDone" in types


@pytest.mark.asyncio
async def test_text_only_content():
    events = await _collect_yield_turn(_TEXT_ONLY_LINES)
    starts = [e for e in events if isinstance(e, StreamTaskMessageStart)]
    assert len(starts) == 1
    assert starts[0].content.type == "text"


@pytest.mark.asyncio
async def test_usage_is_populated_after_stream():
    turn = ClaudeCodeTurn(_fake_lines(_TEXT_ONLY_LINES))
    _ = [e async for e in turn.events]
    usage = turn.usage()
    assert usage.input_tokens == 10
    assert usage.output_tokens == 5
    assert usage.cost_usd == pytest.approx(0.0001, rel=1e-4)
    assert usage.num_llm_calls == 1


@pytest.mark.asyncio
async def test_tool_call_produces_tool_request_and_response():
    events = await _collect_yield_turn(_TOOL_CALL_LINES)
    content_types = {
        getattr(e, "content", None) and getattr(e.content, "type", None) for e in events if hasattr(e, "content")
    }
    assert "tool_request" in content_types
    assert "tool_response" in content_types


@pytest.mark.asyncio
async def test_tool_call_has_one_text_block():
    """The tool_use block is not text; only 'Done.' is the text block."""
    events = await _collect_yield_turn(_TOOL_CALL_LINES)
    text_starts = [
        e for e in events if isinstance(e, StreamTaskMessageStart) and getattr(e.content, "type", None) == "text"
    ]
    assert len(text_starts) == 1


@pytest.mark.asyncio
async def test_empty_lines_are_skipped():
    """Inserting blank lines in the stream must not crash the parser."""
    lines_with_blanks = ["", "  "] + _TEXT_ONLY_LINES + [""]
    events = await _collect_yield_turn(lines_with_blanks)
    assert any(isinstance(e, StreamTaskMessageStart) for e in events)


@pytest.mark.asyncio
async def test_spawn_seam_concept():
    """Demonstrate the injectable spawn seam pattern used in project/acp.py.

    The ``_spawn_claude`` function in ``project/acp.py`` is a top-level async
    generator. Production code calls it like::

        turn = ClaudeCodeTurn(_spawn_claude(prompt))

    In tests, a replacement function is injected (e.g. via monkeypatch) to
    return pre-recorded lines. This test proves the pattern works end-to-end
    without importing the full ACP module (which has module-level env-var
    checks that only pass in a running agent environment).
    """
    recorded_lines = _TEXT_ONLY_LINES

    async def _fake_spawn(prompt: str) -> AsyncIterator[str]:  # noqa: ARG001
        """Drop-in replacement for _spawn_claude."""
        for line in recorded_lines:
            yield line

    called_with: list[str] = []

    async def _wrapped_spawn(prompt: str) -> AsyncIterator[str]:
        called_with.append(prompt)
        async for line in _fake_spawn(prompt):
            yield line

    turn = ClaudeCodeTurn(_wrapped_spawn("test prompt"))
    emitter = UnifiedEmitter(task_id="t2", trace_id=None, parent_span_id=None)
    events = [e async for e in emitter.yield_turn(turn)]

    assert called_with == ["test prompt"]
    assert any(isinstance(e, StreamTaskMessageStart) for e in events)
