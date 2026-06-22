"""Tests for the async (base) Codex harness tutorial agent.

LIVE tests (``TestLiveCodexAgent``):
  - Require the ``codex`` CLI on PATH and ``OPENAI_API_KEY`` set.
  - Skipped automatically when ``CODEX_LIVE_TESTS`` is not set to ``1``.

OFFLINE unit tests (``TestOfflineCodexHandler``):
  - Inject a fake async iterator of pre-recorded codex event lines.
  - Assert ``CodexTurn`` + ``UnifiedEmitter.auto_send_turn`` is driven correctly.
  - Always run.
"""

from __future__ import annotations

import os
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

SAMPLE_EVENTS: list[dict[str, Any]] = [
    {"type": "thread.started", "thread_id": "thread-xyz"},
    {"type": "turn.started"},
    {
        "type": "item.started",
        "item": {"id": "msg-1", "type": "agent_message", "text": "Hi"},
    },
    {
        "type": "item.completed",
        "item": {"id": "msg-1", "type": "agent_message", "text": "Hi there!"},
    },
    {
        "type": "turn.completed",
        "usage": {"input_tokens": 8, "output_tokens": 4, "total_tokens": 12},
    },
]


async def _fake_event_stream():
    """Async iterator of pre-recorded codex event JSON lines (no subprocess)."""
    for evt in SAMPLE_EVENTS:
        yield json.dumps(evt)


class TestOfflineCodexHandler:
    """Unit tests that run without a real codex CLI or network."""

    @pytest.mark.asyncio
    async def test_usage_populated_after_stream_exhausted(self):
        """CodexTurn.usage() returns non-None tokens after stream is exhausted."""
        from agentex.lib.adk import CodexTurn

        turn = CodexTurn(events=_fake_event_stream(), model="o4-mini")

        collected = [e async for e in turn.events]

        usage = turn.usage()
        assert usage.input_tokens == 8
        assert usage.output_tokens == 4
        assert usage.model == "o4-mini"

    @pytest.mark.asyncio
    async def test_auto_send_turn_drives_unified_surface(self):
        """auto_send_turn returns a TurnResult with the final text."""
        from agentex.lib.adk import CodexTurn
        from agentex.lib.core.harness import UnifiedEmitter
        from agentex.types.task_message import TaskMessage
        from agentex.types.text_content import TextContent

        turn = CodexTurn(events=_fake_event_stream(), model="o4-mini")

        real_task_msg = TaskMessage(
            id="msg-fake",
            task_id="t",
            content=TextContent(type="text", author="agent", content=""),
        )

        fake_streaming = MagicMock()
        fake_ctx = AsyncMock()
        fake_ctx.__aenter__ = AsyncMock(return_value=fake_ctx)
        fake_ctx.__aexit__ = AsyncMock(return_value=False)
        fake_ctx.stream_update = AsyncMock(return_value=MagicMock())
        fake_ctx.close = AsyncMock()
        fake_ctx.task_message = real_task_msg
        fake_streaming.streaming_task_message_context = MagicMock(return_value=fake_ctx)

        emitter = UnifiedEmitter(
            task_id="t",
            trace_id=None,
            parent_span_id=None,
            streaming=fake_streaming,
        )

        result = await emitter.auto_send_turn(turn)
        assert result is not None

    @pytest.mark.asyncio
    async def test_session_id_captured_after_stream(self):
        """CodexTurn._result captures the session_id from thread.started."""
        from agentex.lib.adk import CodexTurn

        turn = CodexTurn(events=_fake_event_stream(), model="o4-mini")
        _ = [e async for e in turn.events]

        assert turn._result is not None
        assert turn._result["session_id"] == "thread-xyz"

    @pytest.mark.asyncio
    async def test_yield_turn_is_passthrough(self):
        """yield_turn mode also works with CodexTurn (no streaming infra needed)."""
        from agentex.lib.adk import CodexTurn
        from agentex.lib.core.harness import UnifiedEmitter

        turn = CodexTurn(events=_fake_event_stream(), model="o4-mini")
        emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None)

        events = [e async for e in emitter.yield_turn(turn)]
        assert len(events) > 0


# ---------------------------------------------------------------------------
# Live tests
# ---------------------------------------------------------------------------

LIVE = os.environ.get("CODEX_LIVE_TESTS", "") == "1"
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "ab-harness-codex")


@pytest.mark.skipif(
    not LIVE,
    reason="Set CODEX_LIVE_TESTS=1 and ensure codex CLI + OPENAI_API_KEY are available",
)
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
                    content="What is 3+3? Reply with just the number.",
                    type="text",
                )
            ),
        )
        assert response.result is not None
        assert len(response.result) >= 1
