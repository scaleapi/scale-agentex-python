"""Tests for the Temporal Codex harness tutorial agent.

LIVE tests (``TestLiveCodexAgent``):
  - Require the ``codex`` CLI on PATH, ``OPENAI_API_KEY``, and a running
    Temporal + Agentex server.
  - Skipped automatically when ``CODEX_LIVE_TESTS`` is not set to ``1``.

OFFLINE unit tests (``TestOfflineCodexWorkflow``):
  - Inject a fake async iterator of pre-recorded codex event lines.
  - Assert the signal handler drives ``UnifiedEmitter.auto_send_turn`` and
    captures the codex thread ID on the workflow instance.
  - Always run.
"""

from __future__ import annotations

import os
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

SAMPLE_EVENTS: list[dict[str, Any]] = [
    {"type": "thread.started", "thread_id": "thread-temporal-1"},
    {"type": "turn.started"},
    {
        "type": "item.started",
        "item": {"id": "msg-t1", "type": "agent_message", "text": "Hello"},
    },
    {
        "type": "item.completed",
        "item": {"id": "msg-t1", "type": "agent_message", "text": "Hello from Temporal!"},
    },
    {
        "type": "turn.completed",
        "usage": {"input_tokens": 6, "output_tokens": 3, "total_tokens": 9},
    },
]


async def _fake_event_stream():
    """Async iterator of pre-recorded codex event JSON lines (no subprocess)."""
    for evt in SAMPLE_EVENTS:
        yield json.dumps(evt)


class _FakeSpan:
    id = "span-temporal-1"
    output: Any = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass


class TestOfflineCodexWorkflow:
    """Unit tests that run without a real codex CLI, Temporal, or network."""

    @pytest.mark.asyncio
    async def test_codex_turn_usage_with_temporal_events(self):
        """CodexTurn.usage() is correct after exhausting the temporal sample events."""
        from agentex.lib.adk import CodexTurn

        turn = CodexTurn(events=_fake_event_stream(), model="o4-mini")

        _ = [e async for e in turn.events]

        usage = turn.usage()
        assert usage.input_tokens == 6
        assert usage.output_tokens == 3
        assert usage.model == "o4-mini"

    @pytest.mark.asyncio
    async def test_unified_emitter_auto_send_with_created_at(self):
        """UnifiedEmitter.auto_send_turn accepts created_at=None without error."""
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

        result = await emitter.auto_send_turn(turn, created_at=None)
        assert result is not None

    @pytest.mark.asyncio
    async def test_thread_id_captured_after_exhausted_stream(self):
        """CodexTurn._result captures the thread_id from thread.started."""
        from agentex.lib.adk import CodexTurn

        turn = CodexTurn(events=_fake_event_stream(), model="o4-mini")
        _ = [e async for e in turn.events]

        assert turn._result is not None
        assert turn._result["session_id"] == "thread-temporal-1"

    @pytest.mark.asyncio
    async def test_signal_handler_delegates_to_activity_and_captures_thread_id(self):
        """Signal handler runs the turn via execute_activity, increments the turn
        counter, and captures the codex thread ID returned by the activity."""
        captured: dict[str, Any] = {}

        async def _fake_execute_activity(_activity, params, **_kw):
            captured["params"] = params
            return {
                "session_id": "thread-temporal-1",
                "final_text": "Hello from Temporal!",
                "model": "o4-mini",
            }

        with patch("project.workflow.adk.messages.create", new=AsyncMock()), patch(
            "project.workflow.adk.tracing.span"
        ) as mock_span, patch(
            "project.workflow.workflow.execute_activity", new=_fake_execute_activity
        ), patch("project.workflow.workflow.now", return_value=None):
            mock_span.return_value = _FakeSpan()

            from project.workflow import AtHarnessCodexWorkflow

            wf = AtHarnessCodexWorkflow.__new__(AtHarnessCodexWorkflow)
            wf._turn_number = 0
            wf._codex_thread_id = None
            wf._complete_task = False
            wf._display_name = "test"

            params = MagicMock()
            params.task.id = "task-temporal-offline-1"
            params.event.content.content = "say hello temporal"

            await wf.on_task_event_send(params)

        assert wf._turn_number == 1
        assert wf._codex_thread_id == "thread-temporal-1"
        assert captured["params"].prompt == "say hello temporal"
        assert captured["params"].thread_id is None

    @pytest.mark.asyncio
    async def test_run_codex_turn_activity_streams_and_returns_thread_id(self):
        """The run_codex_turn activity drives the turn and returns the thread id."""
        from agentex.lib.core.harness import UnifiedEmitter

        async def _fake_spawn(model, thread_id=None):  # noqa: ARG001
            fake_stdin = MagicMock()
            fake_stdin.write = MagicMock()
            fake_stdin.drain = AsyncMock()
            fake_stdin.close = MagicMock()
            proc = MagicMock()
            proc.stdin = fake_stdin
            proc.wait = AsyncMock(return_value=0)
            return proc

        async def _fake_process_stdout(_process):  # noqa: ARG001
            for evt in SAMPLE_EVENTS:
                yield json.dumps(evt)

        class _FakeTurnResult:
            final_text = "Hello from Temporal!"

        async def _auto_send(_self, turn, *_a, **_kw):
            async for _ in turn.events:
                pass
            return _FakeTurnResult()

        with patch("project.activities._spawn_codex", new=_fake_spawn), patch(
            "project.activities._process_stdout", new=_fake_process_stdout
        ), patch.object(UnifiedEmitter, "auto_send_turn", new=_auto_send):
            from project.activities import RunCodexTurnParams, run_codex_turn

            result = await run_codex_turn(
                RunCodexTurnParams(
                    task_id="task-temporal-offline-1",
                    prompt="say hello temporal",
                    model="o4-mini",
                )
            )

        assert result["session_id"] == "thread-temporal-1"
        assert result["final_text"] == "Hello from Temporal!"


# ---------------------------------------------------------------------------
# Live tests
# ---------------------------------------------------------------------------

LIVE = os.environ.get("CODEX_LIVE_TESTS", "") == "1"
AGENTEX_API_BASE_URL = os.environ.get("AGENTEX_API_BASE_URL", "http://localhost:5003")
AGENT_NAME = os.environ.get("AGENT_NAME", "at150-codex")


@pytest.mark.skipif(
    not LIVE,
    reason="Set CODEX_LIVE_TESTS=1 and ensure codex CLI + OPENAI_API_KEY + Temporal are available",
)
class TestLiveCodexAgent:
    """End-to-end tests that require the real codex CLI, Temporal, and Agentex server."""

    @pytest.fixture
    def client(self):
        from agentex import Agentex

        return Agentex(base_url=AGENTEX_API_BASE_URL)

    @pytest.fixture
    def agent_id(self, client):
        for agent in client.agents.list():
            if agent.name == AGENT_NAME:
                return agent.id
        raise ValueError(f"Agent {AGENT_NAME!r} not found.")

    def test_send_simple_message(self, client, agent_id: str):
        """Temporal agents process events out of band, so create a task, send an
        event, and poll the task's messages for the agent's response."""
        import time
        import uuid

        from agentex.types import TextContentParam
        from agentex.types.agent_rpc_params import ParamsSendEventRequest, ParamsCreateTaskRequest

        task = client.agents.create_task(agent_id, params=ParamsCreateTaskRequest(name=uuid.uuid1().hex)).result
        assert task is not None

        client.agents.send_event(
            agent_id=agent_id,
            params=ParamsSendEventRequest(
                task_id=task.id,
                content=TextContentParam(
                    author="user",
                    content="What is 5+5? Reply with just the number.",
                    type="text",
                ),
            ),
        )

        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            msgs = client.messages.list(task_id=task.id)
            agent_msgs = [m for m in msgs if getattr(m.content, "author", None) == "agent"]
            response_msgs = [
                m for m in agent_msgs if "Task initialized" not in str(getattr(m.content, "content", ""))
            ]
            if response_msgs:
                assert len(response_msgs) >= 1
                return
            time.sleep(3)

        raise AssertionError("No agent response received within 90 s")
