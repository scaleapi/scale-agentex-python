"""Integration test: Temporal channel with an OpenAI-agents turn, offline.

In a Temporal OpenAI deployment (see
examples/tutorials/10_async/10_temporal/120_openai_agents), the OpenAI Agents
SDK run executes inside a Temporal activity. Each turn's canonical stream is
delivered to Redis via the SAME ``UnifiedEmitter.auto_send_turn`` path used by
the non-temporal async channel — the only temporal-specific concern at the
harness boundary is that the activity stamps messages with a deterministic
``created_at`` (e.g. ``workflow.now()``) so replay is deterministic.

There is no dedicated ``stream_openai_events`` temporal helper (unlike
langgraph's ``stream_langgraph_events``); the temporal OpenAI agent builds an
``OpenAITurn`` and calls ``auto_send_turn`` directly inside the activity. This
suite therefore exercises the auto_send path plus the temporal-only contract:
``created_at`` is threaded through to every streaming context.

What is tested
--------------
- The canonical message sequence (tool_request -> tool_response -> text) is
  delivered via auto_send_turn, exactly as inside a Temporal activity.
- ``created_at`` passed to ``auto_send_turn`` is forwarded to every
  ``streaming_task_message_context`` call (deterministic timestamping).
- Final text is returned from the turn.

What is NOT covered without live infrastructure
-----------------------------------------------
- Temporal scheduling (workflow.signal -> activity dispatch).
- Temporal durability / replay behaviour.
- Redis streaming (requires a running Redis instance).
- A real Runner.run_streamed execution / live OpenAI model behaviour.

See also: test_harness_openai_sync.py and test_harness_openai_async.py.
"""

from __future__ import annotations

from typing import Any
from datetime import datetime, timezone

from agentex.types.text_delta import TextDelta
from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.lib.core.harness.types import StreamTaskMessage
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._openai_turn import OpenAITurn


def _tool_then_text_events() -> list[StreamTaskMessage]:
    return [
        StreamTaskMessageFull(
            type="full",
            index=0,
            content=ToolRequestContent(
                type="tool_request",
                author="agent",
                tool_call_id="call_1",
                name="get_weather",
                arguments={"city": "Paris"},
            ),
        ),
        StreamTaskMessageFull(
            type="full",
            index=1,
            content=ToolResponseContent(
                type="tool_response",
                author="agent",
                tool_call_id="call_1",
                name="get_weather",
                content="The weather in Paris is sunny and 72F",
            ),
        ),
        StreamTaskMessageStart(
            type="start",
            index=2,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageDelta(type="delta", index=2, delta=TextDelta(type="text", text_delta="Sunny ")),
        StreamTaskMessageDelta(type="delta", index=2, delta=TextDelta(type="text", text_delta="and 72F.")),
        StreamTaskMessageDone(type="done", index=2),
    ]


async def _canonical_stream(events: list[StreamTaskMessage]):
    for e in events:
        yield e


# ---------------------------------------------------------------------------
# Fake streaming backend that records the created_at it receives
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


async def _run_activity(events: list[StreamTaskMessage], created_at: datetime | None) -> tuple[Any, _FakeStreaming]:
    """Mirror the temporal activity body: build an OpenAITurn and auto_send it."""
    fake_streaming = _FakeStreaming()
    turn = OpenAITurn(stream=_canonical_stream(events), model="gpt-4o")
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


class TestTemporalActivityMessageOrder:
    async def test_canonical_sequence_delivered(self) -> None:
        _, fake_streaming = await _run_activity(_tool_then_text_events(), created_at=None)
        types = [getattr(m, "type", None) for m in fake_streaming.messages_opened]
        assert "tool_request" in types
        assert "tool_response" in types
        assert types.index("tool_request") < types.index("tool_response")
        assert types[-1] == "text"

    async def test_final_text_returned(self) -> None:
        result, _ = await _run_activity(_tool_then_text_events(), created_at=None)
        assert result.final_text == "Sunny and 72F."


class TestTemporalCreatedAtThreading:
    """created_at is forwarded to every streaming context (deterministic replay)."""

    async def test_created_at_threaded_to_all_contexts(self) -> None:
        fixed = datetime(2026, 6, 22, 12, 0, 0, tzinfo=timezone.utc)
        _, fake_streaming = await _run_activity(_tool_then_text_events(), created_at=fixed)
        assert len(fake_streaming.created_ats) == 3
        assert all(ts == fixed for ts in fake_streaming.created_ats), (
            f"Expected every context stamped with {fixed}, got {fake_streaming.created_ats}"
        )

    async def test_default_created_at_is_none(self) -> None:
        """When the activity does not stamp a timestamp, contexts see None."""
        _, fake_streaming = await _run_activity(_tool_then_text_events(), created_at=None)
        assert all(ts is None for ts in fake_streaming.created_ats)

    async def test_created_at_is_deterministic_across_runs(self) -> None:
        """Two runs with the same created_at stamp identical timestamps — the
        determinism the Temporal channel relies on for replay."""
        fixed = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        _, first = await _run_activity(_tool_then_text_events(), created_at=fixed)
        _, second = await _run_activity(_tool_then_text_events(), created_at=fixed)
        assert first.created_ats == second.created_ats
        assert all(ts == fixed for ts in first.created_ats)
