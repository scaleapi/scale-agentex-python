"""Tests for the sync Codex harness tutorial agent.

LIVE tests (``TestLiveCodexAgent``):
  - Require the ``codex`` CLI on PATH and ``OPENAI_API_KEY`` set.
  - Run the full agent end-to-end against a live Agentex server.
  - Skipped automatically when ``CODEX_LIVE_TESTS`` is not set to ``1``.

OFFLINE unit tests (``TestOfflineCodexHandler``):
  - Inject a fake async iterator of pre-recorded codex event lines.
  - Assert the ``CodexTurn`` + ``UnifiedEmitter`` pipeline yields events,
    populates usage, and satisfies the ``HarnessTurn`` protocol.
  - Always run.
"""

from __future__ import annotations

import os
import json
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

SAMPLE_EVENTS: list[dict[str, Any]] = [
    {"type": "thread.started", "thread_id": "thread-abc"},
    {"type": "turn.started"},
    {
        "type": "item.started",
        "item": {"id": "msg-1", "type": "agent_message", "text": "Hello"},
    },
    {
        "type": "item.completed",
        "item": {"id": "msg-1", "type": "agent_message", "text": "Hello, world!"},
    },
    {
        "type": "turn.completed",
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    },
]


async def _fake_event_stream():
    """Async iterator of pre-recorded codex event JSON lines (no subprocess)."""
    for evt in SAMPLE_EVENTS:
        yield json.dumps(evt)


class TestOfflineCodexHandler:
    """Unit tests that run without a real codex CLI or network."""

    @pytest.mark.asyncio
    async def test_codex_turn_yields_stream_events(self):
        """CodexTurn drives the unified surface and yields StreamTaskMessage* events."""
        from agentex.lib.adk import CodexTurn
        from agentex.lib.core.harness import UnifiedEmitter

        turn = CodexTurn(events=_fake_event_stream(), model="o4-mini")
        emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None)

        events = [e async for e in emitter.yield_turn(turn)]
        assert len(events) > 0, "No events yielded"

        types_seen = {type(e).__name__ for e in events}
        known_types = {
            "StreamTaskMessageStart",
            "StreamTaskMessageDelta",
            "StreamTaskMessageFull",
            "StreamTaskMessageDone",
        }
        assert bool(types_seen & known_types), f"Unexpected event types: {types_seen}"

    @pytest.mark.asyncio
    async def test_usage_populated_after_stream_exhausted(self):
        """CodexTurn.usage() returns correct tokens after stream is exhausted."""
        from agentex.lib.adk import CodexTurn

        turn = CodexTurn(events=_fake_event_stream(), model="o4-mini")

        collected = [e async for e in turn.events]

        usage = turn.usage()
        assert usage.input_tokens == 10
        assert usage.output_tokens == 5
        assert usage.total_tokens == 15
        assert usage.model == "o4-mini"

    @pytest.mark.asyncio
    async def test_codex_turn_protocol_compliance(self):
        """CodexTurn satisfies the HarnessTurn protocol."""
        from agentex.lib.adk import CodexTurn
        from agentex.lib.core.harness.types import HarnessTurn

        turn = CodexTurn(events=_fake_event_stream(), model="o4-mini")
        assert isinstance(turn, HarnessTurn), "CodexTurn does not satisfy HarnessTurn protocol"

    @pytest.mark.asyncio
    async def test_unified_emitter_yield_passes_through_events(self):
        """UnifiedEmitter.yield_turn passes events through unchanged in sync mode."""
        from agentex.lib.adk import CodexTurn
        from agentex.lib.core.harness import UnifiedEmitter

        turn = CodexTurn(events=_fake_event_stream(), model="o4-mini")
        emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None)

        events = [e async for e in emitter.yield_turn(turn)]
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_convert_codex_to_agentex_events_direct(self):
        """convert_codex_to_agentex_events tap produces text start/done events."""
        from agentex.lib.adk import convert_codex_to_agentex_events
        from agentex.types.task_message_update import StreamTaskMessageDone

        events = [e async for e in convert_codex_to_agentex_events(_fake_event_stream())]
        assert any(isinstance(e, StreamTaskMessageDone) for e in events), (
            "Expected at least one StreamTaskMessageDone event"
        )

    @pytest.mark.asyncio
    async def test_on_result_callback_receives_session_id(self):
        """on_result callback receives the session_id from thread.started."""
        from agentex.lib.adk import convert_codex_to_agentex_events

        captured: list[dict] = []

        events = [
            e
            async for e in convert_codex_to_agentex_events(
                _fake_event_stream(),
                on_result=captured.append,
            )
        ]

        assert len(captured) == 1
        assert captured[0]["session_id"] == "thread-abc"
        assert captured[0]["tool_call_count"] == 0


# ---------------------------------------------------------------------------
# Live tests (skipped unless CODEX_LIVE_TESTS=1)
# ---------------------------------------------------------------------------

LIVE = os.environ.get("CODEX_LIVE_TESTS", "") == "1"
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "s070-codex")


@pytest.mark.skipif(not LIVE, reason="Set CODEX_LIVE_TESTS=1 and ensure codex CLI + OPENAI_API_KEY are available")
class TestLiveCodexAgent:
    """End-to-end tests that require the real codex CLI and a running Agentex server."""

    @pytest.fixture
    def client(self):
        from agentex import Agentex

        return Agentex(base_url=AGENTEX_API_BASE_URL)

    def test_send_simple_message(self, client):
        from agentex.types import TextContentParam
        from agentex.types.agent_rpc_params import ParamsSendMessageRequest

        response = client.agents.send_message(
            agent_name=AGENT_NAME,
            params=ParamsSendMessageRequest(
                content=TextContentParam(
                    author="user",
                    content="What is 2+2? Reply with just the number.",
                    type="text",
                )
            ),
        )
        assert response.result is not None
        assert len(response.result) >= 1
