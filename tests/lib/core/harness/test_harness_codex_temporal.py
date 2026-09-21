"""Integration test: Temporal channel with a codex turn, offline.

The codex tap is a pure library adapter (subprocess/sandbox provisioning lives
in the golden agent; there is no codex-specific temporal helper like langgraph's
``stream_langgraph_events``). In a Temporal deployment the codex CLI runs inside
a Temporal activity and the resulting canonical stream is delivered via the SAME
``UnifiedEmitter.auto_send_turn`` path used by the non-temporal async channel.
The only temporal-specific concern at the harness boundary is that the activity
stamps messages with a deterministic ``created_at`` (e.g. ``workflow.now()``)
for replay determinism.

This suite exercises the auto_send path inside an activity-style call plus the
temporal-only contract: ``created_at`` is threaded through to every streaming
context. The native codex event shapes are copied verbatim from the codex turn
test / conformance fixtures.

What is tested
--------------
- The canonical message sequence (tool_request -> tool_response -> text) is
  delivered via auto_send_turn, exactly as inside a Temporal activity.
- ``created_at`` passed to ``auto_send_turn`` is forwarded to every
  ``streaming_task_message_context`` call (deterministic timestamping).
- Final text + usage from turn.completed are returned.

What is NOT covered without live infrastructure
-----------------------------------------------
- Temporal scheduling / durability / replay behaviour.
- Redis streaming (requires a running Redis instance).
- A real codex CLI subprocess / live model behaviour.

See also: test_harness_codex_sync.py and test_harness_codex_async.py.
"""

from __future__ import annotations

from typing import Any, AsyncIterator
from datetime import datetime, timezone

from agentex.types.task_message import TaskMessage
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._codex_turn import CodexTurn


def _tool_then_text_events() -> list[dict[str, Any]]:
    return [
        {"type": "thread.started", "thread_id": "thread-abc"},
        {
            "type": "item.started",
            "item": {"id": "tool1", "type": "command_execution", "command": "cat weather.txt"},
        },
        {
            "type": "item.completed",
            "item": {
                "id": "tool1",
                "type": "command_execution",
                "command": "cat weather.txt",
                "aggregated_output": "sunny and 72F",
                "exit_code": 0,
            },
        },
        {"type": "item.started", "item": {"id": "msg1", "type": "agent_message", "text": ""}},
        {
            "type": "item.completed",
            "item": {"id": "msg1", "type": "agent_message", "text": "The weather is sunny and 72F."},
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 20, "output_tokens": 8, "total_tokens": 28},
        },
    ]


async def _aiter(events: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for e in events:
        yield e


# ---------------------------------------------------------------------------
# Fake streaming backend that records created_at
# ---------------------------------------------------------------------------


class _FakeCtx:
    def __init__(self, ctype: str, initial_content: Any) -> None:
        self.ctype = ctype
        self.task_message = TaskMessage(id="msg-1", task_id="task1", content=initial_content)

    async def __aenter__(self) -> "_FakeCtx":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        await self.close()
        return False

    async def close(self) -> None:
        pass

    async def stream_update(self, update: Any) -> Any:
        return update


class _FakeStreaming:
    def __init__(self) -> None:
        self.messages_opened: list[Any] = []
        self.created_ats: list[Any] = []

    def streaming_task_message_context(
        self,
        task_id: str,
        initial_content: Any,
        streaming_mode: str = "coalesced",
        created_at: Any = None,
    ) -> _FakeCtx:
        ctype = getattr(initial_content, "type", None) or ""
        self.messages_opened.append(initial_content)
        self.created_ats.append(created_at)
        return _FakeCtx(ctype, initial_content)


async def _run_activity(events: list[dict[str, Any]], created_at: datetime | None) -> tuple[Any, _FakeStreaming]:
    fake_streaming = _FakeStreaming()
    turn = CodexTurn(_aiter(events), model="o4-mini")
    emitter = UnifiedEmitter(
        task_id="task1",
        trace_id=None,
        parent_span_id=None,
        tracer=False,
        streaming=fake_streaming,
    )
    result = await emitter.auto_send_turn(turn, created_at=created_at)
    return result, fake_streaming


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTemporalActivityDelivery:
    async def test_canonical_sequence_delivered(self) -> None:
        _, fake_streaming = await _run_activity(_tool_then_text_events(), created_at=None)
        types = [getattr(m, "type", None) for m in fake_streaming.messages_opened]
        assert "tool_request" in types
        assert "tool_response" in types
        assert types.index("tool_request") < types.index("tool_response")
        assert types[-1] == "text"

    async def test_tool_round_trip_keyed_correctly(self) -> None:
        _, fake_streaming = await _run_activity(_tool_then_text_events(), created_at=None)
        tool_req = next(m for m in fake_streaming.messages_opened if isinstance(m, ToolRequestContent))
        tool_resp = next(m for m in fake_streaming.messages_opened if isinstance(m, ToolResponseContent))
        assert tool_req.tool_call_id == tool_resp.tool_call_id

    async def test_final_text_and_usage(self) -> None:
        result, _ = await _run_activity(_tool_then_text_events(), created_at=None)
        assert result.final_text == "The weather is sunny and 72F."
        assert result.usage.total_tokens == 28
        assert result.usage.num_tool_calls == 1


class TestTemporalCreatedAtThreading:
    async def test_created_at_threaded_to_all_contexts(self) -> None:
        fixed = datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc)
        _, fake_streaming = await _run_activity(_tool_then_text_events(), created_at=fixed)
        assert len(fake_streaming.created_ats) == len(fake_streaming.messages_opened)
        assert all(ts == fixed for ts in fake_streaming.created_ats), (
            f"Expected every context stamped with {fixed}, got {fake_streaming.created_ats}"
        )

    async def test_default_created_at_is_none(self) -> None:
        _, fake_streaming = await _run_activity(_tool_then_text_events(), created_at=None)
        assert all(ts is None for ts in fake_streaming.created_ats)

    async def test_created_at_deterministic_across_runs(self) -> None:
        fixed = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        _, first = await _run_activity(_tool_then_text_events(), created_at=fixed)
        _, second = await _run_activity(_tool_then_text_events(), created_at=fixed)
        assert first.created_ats == second.created_ats
