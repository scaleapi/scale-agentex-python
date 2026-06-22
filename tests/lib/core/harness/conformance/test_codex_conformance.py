"""Conformance fixtures for the codex harness tap.

Each fixture is derived from a ``CodexTurn`` and registered into the
cross-channel conformance runner so that span derivation is validated
alongside all other harness taps.

Following the per-module registry pattern from runner.py: this module keeps
its own local list of fixtures, both registers them AND parametrizes over
them, to guarantee determinism regardless of pytest collection order.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

import pytest

from agentex.lib.core.harness.types import StreamTaskMessage
from agentex.lib.adk._modules._codex_sync import convert_codex_to_agentex_events

from .runner import Fixture, register, derive_all


async def _aiter(items: list[Any]) -> AsyncIterator[Any]:
    for item in items:
        yield item


async def _collect(events: list[Any]) -> list[StreamTaskMessage]:
    return [msg async for msg in convert_codex_to_agentex_events(_aiter(events))]


def _build(events: list[Any]) -> list[StreamTaskMessage]:
    return asyncio.run(_collect(events))


# ---------------------------------------------------------------------------
# Fixture 1: plain text response
# ---------------------------------------------------------------------------

_CODEX_TEXT = Fixture(
    name="codex-text",
    events=_build(
        [
            {"type": "thread.started", "thread_id": "thread-abc"},
            {"type": "turn.started"},
            {
                "type": "item.started",
                "item": {"id": "msg1", "type": "agent_message", "text": "Hello"},
            },
            {
                "type": "item.updated",
                "item": {"id": "msg1", "type": "agent_message", "text": "Hello, world"},
            },
            {
                "type": "item.completed",
                "item": {"id": "msg1", "type": "agent_message", "text": "Hello, world!"},
            },
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            },
        ]
    ),
)
register(_CODEX_TEXT)

# ---------------------------------------------------------------------------
# Fixture 2: tool call (command_execution)
# ---------------------------------------------------------------------------

_CODEX_TOOL = Fixture(
    name="codex-tool-command",
    events=_build(
        [
            {"type": "thread.started", "thread_id": "thread-cmd"},
            {
                "type": "item.started",
                "item": {
                    "id": "tool1",
                    "type": "command_execution",
                    "command": "ls /workspace",
                },
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "tool1",
                    "type": "command_execution",
                    "command": "ls /workspace",
                    "aggregated_output": "file1.txt\nfile2.py",
                    "exit_code": 0,
                },
            },
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 20, "output_tokens": 8, "total_tokens": 28},
            },
        ]
    ),
)
register(_CODEX_TOOL)

# ---------------------------------------------------------------------------
# Fixture 3: reasoning block
# ---------------------------------------------------------------------------

_CODEX_REASONING = Fixture(
    name="codex-reasoning",
    events=_build(
        [
            {"type": "thread.started", "thread_id": "thread-reason"},
            {
                "type": "item.started",
                "item": {"id": "r1", "type": "reasoning", "text": ""},
            },
            {
                "type": "item.updated",
                "item": {"id": "r1", "type": "reasoning", "text": "Step 1: analyze the problem"},
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "r1",
                    "type": "reasoning",
                    "text": "Step 1: analyze the problem\nStep 2: solve it",
                },
            },
            {
                "type": "item.started",
                "item": {"id": "msg2", "type": "agent_message", "text": ""},
            },
            {
                "type": "item.completed",
                "item": {"id": "msg2", "type": "agent_message", "text": "The answer is 42."},
            },
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 30,
                    "output_tokens": 20,
                    "reasoning_tokens": 50,
                    "total_tokens": 100,
                },
            },
        ]
    ),
)
register(_CODEX_REASONING)

# ---------------------------------------------------------------------------
# Fixture 4: multi-step (mcp_tool_call + follow-up text)
# ---------------------------------------------------------------------------

_CODEX_MULTI = Fixture(
    name="codex-multi-step",
    events=_build(
        [
            {"type": "thread.started", "thread_id": "thread-multi"},
            {
                "type": "item.started",
                "item": {
                    "id": "mcp1",
                    "type": "mcp_tool_call",
                    "server": "filesystem",
                    "tool": "read_file",
                    "arguments": {"path": "/workspace/README.md"},
                },
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "mcp1",
                    "type": "mcp_tool_call",
                    "server": "filesystem",
                    "tool": "read_file",
                    "arguments": {"path": "/workspace/README.md"},
                    "result": {"content": "# My Project"},
                },
            },
            {
                "type": "item.started",
                "item": {"id": "msg3", "type": "agent_message", "text": "The README says:"},
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "msg3",
                    "type": "agent_message",
                    "text": "The README says: # My Project",
                },
            },
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 50, "output_tokens": 30, "total_tokens": 80},
            },
        ]
    ),
)
register(_CODEX_MULTI)


# ---------------------------------------------------------------------------
# Local parametrized tests (cross-channel conformance)
# ---------------------------------------------------------------------------

_LOCAL_FIXTURES = [_CODEX_TEXT, _CODEX_TOOL, _CODEX_REASONING, _CODEX_MULTI]


@pytest.mark.parametrize("fixture", _LOCAL_FIXTURES, ids=lambda f: f.name)
def test_codex_span_derivation_is_deterministic(fixture: Fixture) -> None:
    """Span derivation over codex events is deterministic (cross-channel guarantee).

    Deriving twice over the same events yields identical signals. This is the
    invariant that makes ``yield`` and ``auto_send`` delivery equivalent: both
    observe the same event stream, so their tracing side effects are identical.
    """
    assert derive_all(fixture.events) == derive_all(fixture.events)


@pytest.mark.parametrize("fixture", _LOCAL_FIXTURES, ids=lambda f: f.name)
def test_codex_events_are_non_empty(fixture: Fixture) -> None:
    """Every codex fixture yields at least one StreamTaskMessage*."""
    assert len(fixture.events) > 0
