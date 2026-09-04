"""Tests for the sync Claude Code tutorial agent.

LIVE tests (``TestClaudeCodeLive``):
  - Require the ``claude`` CLI on PATH and ``ANTHROPIC_API_KEY`` set.
  - Run the full agent end-to-end against a live Agentex server.
  - Skipped automatically when ``CLAUDE_LIVE_TESTS`` is not set to ``1``.

OFFLINE unit tests (``TestClaudeCodeOffline``):
  - Inject a fake async iterator of pre-recorded stream-json lines.
  - Assert the ``ClaudeCodeTurn`` + ``UnifiedEmitter`` pipeline yields events,
    populates usage, and satisfies the ``HarnessTurn`` protocol.
  - Always run -- no CLI or API key needed.
"""

from __future__ import annotations

import os
import json
from typing import AsyncIterator

import pytest

# ---------------------------------------------------------------------------
# Recorded stream-json fixtures
# ---------------------------------------------------------------------------

_TEXT_ONLY_LINES: list[str] = [
    json.dumps({"type": "system", "subtype": "init", "session_id": "sess-offline-1"}),
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


async def _fake_lines(lines: list[str]) -> AsyncIterator[str]:
    """Async iterator of pre-recorded stream-json lines (no subprocess)."""
    for line in lines:
        yield line


# ---------------------------------------------------------------------------
# Offline tests (always run -- no CLI or API key needed)
# ---------------------------------------------------------------------------


class TestClaudeCodeOffline:
    """Unit tests that run without a real claude CLI or network."""

    @pytest.mark.asyncio
    async def test_yields_stream_events(self):
        """ClaudeCodeTurn drives UnifiedEmitter and yields StreamTaskMessage* events."""
        from agentex.lib.adk import ClaudeCodeTurn
        from agentex.lib.core.harness import UnifiedEmitter
        from agentex.types.task_message_update import StreamTaskMessageStart

        turn = ClaudeCodeTurn(_fake_lines(_TEXT_ONLY_LINES))
        emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None)

        events = [e async for e in emitter.yield_turn(turn)]
        assert len(events) > 0, "No events yielded"
        assert any(isinstance(e, StreamTaskMessageStart) for e in events)

    @pytest.mark.asyncio
    async def test_stream_task_message_done_present(self):
        """StreamTaskMessageDone must appear after stream exhaustion."""
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
    async def test_usage_populated_after_stream_exhausted(self):
        """ClaudeCodeTurn.usage() returns correct tokens after stream is exhausted."""
        from agentex.lib.adk import ClaudeCodeTurn

        turn = ClaudeCodeTurn(_fake_lines(_TEXT_ONLY_LINES))
        _ = [e async for e in turn.events]
        usage = turn.usage()
        assert usage.input_tokens == 10
        assert usage.output_tokens == 5
        assert usage.num_llm_calls == 1

    @pytest.mark.asyncio
    async def test_protocol_compliance(self):
        """ClaudeCodeTurn satisfies the HarnessTurn protocol."""
        from agentex.lib.adk import ClaudeCodeTurn

        turn = ClaudeCodeTurn(_fake_lines(_TEXT_ONLY_LINES))
        assert hasattr(turn, "events"), "ClaudeCodeTurn missing .events"
        assert hasattr(turn, "usage"), "ClaudeCodeTurn missing .usage()"


# ---------------------------------------------------------------------------
# Live tests (skipped unless CLAUDE_LIVE_TESTS=1)
# ---------------------------------------------------------------------------

pytestmark_live = pytest.mark.skipif(
    not os.environ.get("CLAUDE_LIVE_TESTS"),
    reason="Set CLAUDE_LIVE_TESTS=1 and ensure the `claude` CLI + ANTHROPIC_API_KEY are available",
)

AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "s060-claude-code")


@pytestmark_live
class TestClaudeCodeLive:
    """Live streaming tests -- needs the claude CLI + ANTHROPIC_API_KEY."""

    @pytest.fixture
    def client(self):
        from agentex import Agentex

        return Agentex(base_url=AGENTEX_API_BASE_URL)

    @pytest.fixture
    def agent_name(self):
        return AGENT_NAME

    def test_stream_simple_message(self, client, agent_name: str):
        """Stream a simple prompt through the local Claude Code subprocess."""
        from test_utils.sync import collect_streaming_response

        from agentex.types import TextContentParam
        from agentex.types.agent_rpc_params import ParamsSendMessageRequest

        stream = client.agents.send_message_stream(
            agent_name=agent_name,
            params=ParamsSendMessageRequest(
                content=TextContentParam(
                    author="user",
                    content="Reply with exactly three words: hello from claude",
                    type="text",
                )
            ),
        )
        aggregated_content, chunks = collect_streaming_response(stream)
        assert aggregated_content is not None
        assert len(chunks) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
