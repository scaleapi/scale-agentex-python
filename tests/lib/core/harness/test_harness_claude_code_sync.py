"""Integration test: sync (HTTP-yield) channel with a claude-code turn.

Exercises the unified harness surface (UnifiedEmitter.yield_turn + ClaudeCodeTurn)
with hand-built claude-code ``stream-json`` envelopes so the test runs fully
offline (no claude-code CLI subprocess, no API keys, no Agentex server).

Native stream shapes
---------------------
``ClaudeCodeTurn`` consumes an async iterator of raw claude-code stream-json
envelopes (str | dict). The envelope shapes used here are copied verbatim from
the claude-code turn test (tests/lib/adk/test_claude_code_turn.py) and the
claude-code conformance fixtures
(tests/lib/core/harness/conformance/test_claude_code_conformance.py):

    assistant text block  -> Start(TextContent) + Delta + Done
    assistant tool_use    -> Start(ToolRequestContent) + Done
    user tool_result      -> Full(ToolResponseContent)
    assistant thinking    -> Start(ReasoningContent) + Delta + Done

What is tested
--------------
- The sync handler forwards StreamTaskMessage* events in canonical order:
  tool_request (Start+Done) -> tool_response (Full) -> text.
- The tool_response carries the tool_result content, keyed by tool_use_id.
- With a trace_id + fake tracing, the SpanDeriver opens a tool span on
  Done(tool_request) and closes it on the matching Full(tool_response), and
  opens/closes a reasoning span for a thinking block.

What is NOT covered without live infrastructure
-----------------------------------------------
- Actual HTTP streaming over the ACP sync endpoint.
- A real claude-code CLI subprocess / live model behaviour.
- The full FastACP request/response lifecycle.

See also: test_harness_claude_code_async.py and test_harness_claude_code_temporal.py.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, override

from tests.lib.core.harness._fakes import FakeTracing
from agentex.lib.core.harness.types import OpenSpan, CloseSpan
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._claude_code_turn import ClaudeCodeTurn

# ---------------------------------------------------------------------------
# Native claude-code envelope fixtures (copied from the turn + conformance tests)
# ---------------------------------------------------------------------------


def _tool_then_text_envelopes() -> list[dict[str, Any]]:
    """tool_use -> tool_result -> final text, then a result envelope with usage."""
    return [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_read",
                        "name": "Read",
                        "input": {"path": "/workspace/README.md"},
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_read",
                        "content": "# My Project — temperature 72F",
                    }
                ]
            },
        },
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "The project file says 72F."}]},
        },
        {
            "type": "result",
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "cost_usd": 0.01,
            "num_turns": 2,
        },
    ]


def _thinking_envelopes() -> list[dict[str, Any]]:
    return [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "thinking", "thinking": "Let me think.\nStep 1: check the facts."},
                    {"type": "text", "text": "Here is my answer."},
                ]
            },
        },
        {"type": "result", "usage": {"input_tokens": 10, "output_tokens": 5}},
    ]


async def _aiter(envelopes: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for e in envelopes:
        yield e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_yield_turn(
    envelopes: list[dict[str, Any]],
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    fake_tracing: FakeTracing | None = None,
) -> list[Any]:
    tracer: SpanTracer | bool | None = None
    if trace_id and fake_tracing is not None:
        tracer = SpanTracer(
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            task_id="task1",
            tracing=fake_tracing,
        )

    turn = ClaudeCodeTurn(_aiter(envelopes))
    emitter = UnifiedEmitter(
        task_id="task1",
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        tracer=tracer if tracer is not None else False,
    )
    return [ev async for ev in emitter.yield_turn(turn)]


# ---------------------------------------------------------------------------
# Tests: event order and content
# ---------------------------------------------------------------------------


class TestSyncYieldEventOrder:
    async def test_tool_request_precedes_tool_response(self) -> None:
        events = await _run_yield_turn(_tool_then_text_envelopes())
        content_types = [
            getattr(getattr(ev, "content", None), "type", None)
            for ev in events
            if isinstance(ev, (StreamTaskMessageStart, StreamTaskMessageFull))
        ]
        assert "tool_request" in content_types
        assert "tool_response" in content_types
        assert content_types.index("tool_request") < content_types.index("tool_response")

    async def test_text_appears_after_tool_response(self) -> None:
        events = await _run_yield_turn(_tool_then_text_envelopes())
        tool_resp_pos = next(
            i
            for i, ev in enumerate(events)
            if isinstance(ev, StreamTaskMessageFull)
            and getattr(getattr(ev, "content", None), "type", None) == "tool_response"
        )
        text_start_pos = next(
            i
            for i, ev in enumerate(events)
            if isinstance(ev, StreamTaskMessageStart) and getattr(getattr(ev, "content", None), "type", None) == "text"
        )
        assert tool_resp_pos < text_start_pos

    async def test_tool_response_carries_result_keyed_by_tool_use_id(self) -> None:
        events = await _run_yield_turn(_tool_then_text_envelopes())
        full_responses = [
            ev.content
            for ev in events
            if isinstance(ev, StreamTaskMessageFull) and isinstance(getattr(ev, "content", None), ToolResponseContent)
        ]
        assert len(full_responses) == 1
        tool_response = full_responses[0]
        assert isinstance(tool_response, ToolResponseContent)
        assert tool_response.tool_call_id == "call_read"
        assert "72F" in str(tool_response.content)

    async def test_tool_request_is_read(self) -> None:
        events = await _run_yield_turn(_tool_then_text_envelopes())
        tool_reqs = [
            ev.content
            for ev in events
            if isinstance(getattr(ev, "content", None), ToolRequestContent)
        ]
        assert any(isinstance(c, ToolRequestContent) and c.name == "Read" for c in tool_reqs)

    async def test_every_start_has_matching_done(self) -> None:
        events = await _run_yield_turn(_tool_then_text_envelopes())
        starts = {ev.index for ev in events if isinstance(ev, StreamTaskMessageStart)}
        dones = {ev.index for ev in events if isinstance(ev, StreamTaskMessageDone)}
        assert starts == dones, f"Unmatched Start/Done indices: starts={starts} dones={dones}"


# ---------------------------------------------------------------------------
# Tests: span derivation on the yield path
# ---------------------------------------------------------------------------


class TestSyncYieldSpanDerivation:
    async def test_tool_span_opened_and_closed(self) -> None:
        """Done(tool_request) opens a tool span; Full(tool_response) closes it."""
        fake_tracing = FakeTracing()
        await _run_yield_turn(
            _tool_then_text_envelopes(),
            trace_id="trace1",
            parent_span_id="parent-span",
            fake_tracing=fake_tracing,
        )
        assert len(fake_tracing.started) == 1
        assert len(fake_tracing.ended) == 1
        name, parent_id, _ = fake_tracing.started[0]
        assert name == "Read"
        assert parent_id == "parent-span"

    async def test_tool_span_output_is_tool_result(self) -> None:
        fake_tracing = FakeTracing()
        await _run_yield_turn(
            _tool_then_text_envelopes(),
            trace_id="trace1",
            parent_span_id="parent-span",
            fake_tracing=fake_tracing,
        )
        name, output = fake_tracing.ended[0]
        assert name == "Read"
        assert "72F" in str(output)

    async def test_reasoning_span_for_thinking_block(self) -> None:
        """A thinking block opens and closes a reasoning span."""
        fake_tracing = FakeTracing()
        await _run_yield_turn(
            _thinking_envelopes(),
            trace_id="trace1",
            parent_span_id="parent-span",
            fake_tracing=fake_tracing,
        )
        assert fake_tracing.started_names == ["reasoning"]
        assert len(fake_tracing.ended) == 1

    async def test_no_trace_id_means_no_spans(self) -> None:
        fake_tracing = FakeTracing()
        turn = ClaudeCodeTurn(_aiter(_tool_then_text_envelopes()))
        emitter = UnifiedEmitter(task_id="task1", trace_id=None, parent_span_id=None, tracing=fake_tracing)
        [_ async for _ in emitter.yield_turn(turn)]
        assert fake_tracing.started == []
        assert fake_tracing.ended == []

    async def test_tracer_false_suppresses_spans(self) -> None:
        fake_tracing = FakeTracing()
        turn = ClaudeCodeTurn(_aiter(_tool_then_text_envelopes()))
        emitter = UnifiedEmitter(
            task_id="task1",
            trace_id="trace1",
            parent_span_id="parent-span",
            tracer=False,
            tracing=fake_tracing,
        )
        [_ async for _ in emitter.yield_turn(turn)]
        assert fake_tracing.started == []
        assert fake_tracing.ended == []

    async def test_span_signal_types(self) -> None:
        received_signals: list[Any] = []

        class _RecordingTracer(SpanTracer):
            @override
            async def handle(self, signal: Any) -> None:
                received_signals.append(signal)
                await super().handle(signal)

        fake_tracing = FakeTracing()
        tracer = _RecordingTracer(
            trace_id="trace1",
            parent_span_id="parent",
            task_id="task1",
            tracing=fake_tracing,
        )
        turn = ClaudeCodeTurn(_aiter(_tool_then_text_envelopes()))
        emitter = UnifiedEmitter(task_id="task1", trace_id="trace1", parent_span_id="parent", tracer=tracer)
        [_ async for _ in emitter.yield_turn(turn)]

        tool_signals = [s for s in received_signals if getattr(s, "name", None) == "Read"]
        assert len(tool_signals) >= 1
        assert isinstance(received_signals[0], OpenSpan)
        assert any(isinstance(s, CloseSpan) for s in received_signals)
