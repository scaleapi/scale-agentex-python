"""End-to-end: GeminiCliTurn through UnifiedEmitter.yield_turn (sync HTTP path).

Checks event order and content, and that tool spans are derived from the
canonical stream the Gemini CLI tap produces.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._gemini_cli_turn import GeminiCliTurn

from ._fakes import FakeTracing


def _tool_then_text_events() -> list[dict[str, Any]]:
    return [
        {"type": "init", "session_id": "s", "model": "gemini-2.5-flash"},
        {"type": "message", "role": "user", "content": "What is in a.txt?"},
        {"type": "tool_use", "tool_name": "read_file", "tool_id": "call-1", "parameters": {"path": "a.txt"}},
        {"type": "tool_result", "tool_id": "call-1", "status": "success", "output": "hello"},
        {"type": "message", "role": "assistant", "content": "It says ", "delta": True},
        {"type": "message", "role": "assistant", "content": "hello.", "delta": True},
        {"type": "result", "status": "success", "stats": {"input_tokens": 5, "output_tokens": 3, "tool_calls": 1}},
    ]


async def _aiter(events: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for e in events:
        yield e


async def _run_yield_turn(
    events: list[dict[str, Any]],
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    fake_tracing: FakeTracing | None = None,
) -> tuple[list[Any], GeminiCliTurn]:
    tracer: SpanTracer | bool | None = None
    if trace_id and fake_tracing is not None:
        tracer = SpanTracer(trace_id=trace_id, parent_span_id=parent_span_id, task_id="task1", tracing=fake_tracing)
    turn = GeminiCliTurn(_aiter(events))
    emitter = UnifiedEmitter(
        task_id="task1",
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        tracer=tracer if tracer is not None else False,
    )
    return [ev async for ev in emitter.yield_turn(turn)], turn


class TestSyncYieldEventOrder:
    async def test_tool_request_precedes_tool_response_then_text(self) -> None:
        out, _ = await _run_yield_turn(_tool_then_text_events())
        kinds = [type(e).__name__ for e in out]
        assert kinds.index("StreamTaskMessageFull") > kinds.index("StreamTaskMessageStart")
        req = [e for e in out if isinstance(e, StreamTaskMessageStart) and isinstance(e.content, ToolRequestContent)][0]
        res = [e for e in out if isinstance(e, StreamTaskMessageFull)][0]
        assert isinstance(res.content, ToolResponseContent)
        assert req.content.tool_call_id == res.content.tool_call_id == "call-1"
        text_start = [
            e for e in out if isinstance(e, StreamTaskMessageStart) and not isinstance(e.content, ToolRequestContent)
        ][0]
        assert out.index(text_start) > out.index(res)

    async def test_every_start_has_matching_done(self) -> None:
        out, _ = await _run_yield_turn(_tool_then_text_events())
        starts = {e.index for e in out if isinstance(e, StreamTaskMessageStart)}
        dones = {e.index for e in out if isinstance(e, StreamTaskMessageDone)}
        assert starts == dones

    async def test_usage_available_after_turn(self) -> None:
        _, turn = await _run_yield_turn(_tool_then_text_events())
        usage = turn.usage()
        assert usage.input_tokens == 5 and usage.output_tokens == 3 and usage.num_tool_calls == 1
        assert usage.model == "gemini-2.5-flash"


class TestSyncYieldSpanDerivation:
    async def test_tool_span_opened_and_closed_with_result(self) -> None:
        fake = FakeTracing()
        await _run_yield_turn(_tool_then_text_events(), trace_id="trace1", parent_span_id="parent", fake_tracing=fake)
        assert "read_file" in fake.started_names
        assert any(isinstance(o, dict) and o.get("result") == "hello" for o in fake.ended_outputs)

    async def test_no_trace_id_means_no_spans(self) -> None:
        fake = FakeTracing()
        await _run_yield_turn(_tool_then_text_events(), trace_id=None, fake_tracing=fake)
        assert fake.started == []
