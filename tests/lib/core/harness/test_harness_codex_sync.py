"""Integration test: sync (HTTP-yield) channel with a codex turn.

Exercises the unified harness surface (UnifiedEmitter.yield_turn + CodexTurn)
with hand-built codex ``exec --json`` event dicts so the test runs fully offline
(no codex CLI subprocess, no API keys, no Agentex server).

Native stream shapes
---------------------
``CodexTurn`` consumes an async iterator of raw codex events (str | dict). The
event shapes used here are copied verbatim from the codex turn test
(tests/lib/adk/test_codex_turn.py) and the codex conformance fixtures
(tests/lib/core/harness/conformance/test_codex_conformance.py):

    command_execution item -> Start(ToolRequestContent) + Done + Full(ToolResponseContent)
    agent_message item     -> Start(TextContent) + ... + Full/Done
    reasoning item         -> Start(ReasoningContent) + Full(ReasoningContent)
    turn.completed         -> usage

Reasoning note
--------------
The codex converter emits reasoning as Start(ReasoningContent) + Full(ReasoningContent)
with NO Done event. The SpanDeriver opens a reasoning span on Start but only
closes it on a Done; with no Done, the reasoning span is closed by flush() at
end of stream (is_complete=False). This is asserted explicitly below rather than
glossed over — it is a real codex-specific quirk, not a missing channel.

What is tested
--------------
- The sync handler forwards StreamTaskMessage* events in canonical order:
  tool_request (Start+Done) -> tool_response (Full) -> text.
- The tool_response carries the command output, keyed by item id.
- With a trace_id + fake tracing, a tool span is opened on Done(tool_request)
  and closed on the matching Full(tool_response), and a reasoning span is
  opened (closed-by-flush) for a reasoning item.

What is NOT covered without live infrastructure
-----------------------------------------------
- Actual HTTP streaming over the ACP sync endpoint.
- A real codex CLI subprocess / live model behaviour.
- The full FastACP request/response lifecycle.

See also: test_harness_codex_async.py and test_harness_codex_temporal.py.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, override

from agentex.lib.core.harness.types import OpenSpan, CloseSpan
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.task_message_update import (
    StreamTaskMessageFull,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._codex_turn import CodexTurn

from ._fakes import FakeTracing

# ---------------------------------------------------------------------------
# Native codex event fixtures (copied from the turn + conformance tests)
# ---------------------------------------------------------------------------


def _tool_then_text_events() -> list[dict[str, Any]]:
    """A command_execution tool round-trip followed by a final text reply."""
    return [
        {"type": "thread.started", "thread_id": "thread-abc"},
        {"type": "turn.started"},
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


def _reasoning_events() -> list[dict[str, Any]]:
    return [
        {"type": "thread.started", "thread_id": "thread-reason"},
        {"type": "item.started", "item": {"id": "r1", "type": "reasoning", "text": ""}},
        {
            "type": "item.completed",
            "item": {"id": "r1", "type": "reasoning", "text": "Step 1: analyze\nStep 2: solve"},
        },
        {"type": "item.started", "item": {"id": "msg2", "type": "agent_message", "text": ""}},
        {"type": "item.completed", "item": {"id": "msg2", "type": "agent_message", "text": "42"}},
        {"type": "turn.completed", "usage": {"input_tokens": 30, "output_tokens": 20, "total_tokens": 50}},
    ]


async def _aiter(events: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for e in events:
        yield e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_yield_turn(
    events: list[dict[str, Any]],
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

    turn = CodexTurn(_aiter(events), model="o4-mini")
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
        events = await _run_yield_turn(_tool_then_text_events())
        content_types = [
            getattr(getattr(ev, "content", None), "type", None)
            for ev in events
            if isinstance(ev, (StreamTaskMessageStart, StreamTaskMessageFull))
        ]
        assert "tool_request" in content_types
        assert "tool_response" in content_types
        assert content_types.index("tool_request") < content_types.index("tool_response")

    async def test_text_appears_after_tool_response(self) -> None:
        events = await _run_yield_turn(_tool_then_text_events())
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

    async def test_tool_response_carries_command_output(self) -> None:
        events = await _run_yield_turn(_tool_then_text_events())
        full_responses = [
            ev.content
            for ev in events
            if isinstance(ev, StreamTaskMessageFull) and isinstance(getattr(ev, "content", None), ToolResponseContent)
        ]
        assert len(full_responses) == 1
        tool_response = full_responses[0]
        assert isinstance(tool_response, ToolResponseContent)
        assert "72F" in str(tool_response.content)

    async def test_tool_request_present(self) -> None:
        events = await _run_yield_turn(_tool_then_text_events())
        tool_reqs = [
            ev.content for ev in events if isinstance(getattr(ev, "content", None), ToolRequestContent)
        ]
        assert len(tool_reqs) == 1


# ---------------------------------------------------------------------------
# Tests: span derivation on the yield path
# ---------------------------------------------------------------------------


class TestSyncYieldSpanDerivation:
    async def test_tool_span_opened_and_closed(self) -> None:
        """Done(tool_request) opens a tool span; Full(tool_response) closes it."""
        fake_tracing = FakeTracing()
        await _run_yield_turn(
            _tool_then_text_events(),
            trace_id="trace1",
            parent_span_id="parent-span",
            fake_tracing=fake_tracing,
        )
        assert len(fake_tracing.started) == 1
        assert len(fake_tracing.ended) == 1
        _name, parent_id, _input = fake_tracing.started[0]
        assert parent_id == "parent-span"

    async def test_tool_span_output_is_command_output(self) -> None:
        fake_tracing = FakeTracing()
        await _run_yield_turn(
            _tool_then_text_events(),
            trace_id="trace1",
            parent_span_id="parent-span",
            fake_tracing=fake_tracing,
        )
        _name, output = fake_tracing.ended[0]
        assert "72F" in str(output)

    async def test_reasoning_span_opened_then_flush_closed(self) -> None:
        """A codex reasoning item emits Start+Full (no Done): the reasoning span
        opens and is closed by flush() at end of stream (is_complete=False)."""
        received_signals: list[Any] = []

        class _RecordingTracer(SpanTracer):
            @override
            async def handle(self, signal: Any) -> None:
                received_signals.append(signal)
                await super().handle(signal)

        fake_tracing = FakeTracing()
        tracer = _RecordingTracer(
            trace_id="trace1",
            parent_span_id="parent-span",
            task_id="task1",
            tracing=fake_tracing,
        )
        turn = CodexTurn(_aiter(_reasoning_events()), model="o4-mini")
        emitter = UnifiedEmitter(task_id="task1", trace_id="trace1", parent_span_id="parent-span", tracer=tracer)
        [_ async for _ in emitter.yield_turn(turn)]

        opens = [s for s in received_signals if isinstance(s, OpenSpan) and s.kind == "reasoning"]
        closes = [s for s in received_signals if isinstance(s, CloseSpan) and str(s.key).startswith("reasoning:")]
        assert len(opens) == 1, "Reasoning Start must open exactly one reasoning span"
        assert len(closes) == 1, "Reasoning span must be closed (by flush) at end of stream"
        assert closes[0].is_complete is False, "No Done event, so the reasoning span is flush-closed as incomplete"

    async def test_no_trace_id_means_no_spans(self) -> None:
        fake_tracing = FakeTracing()
        turn = CodexTurn(_aiter(_tool_then_text_events()), model="o4-mini")
        emitter = UnifiedEmitter(task_id="task1", trace_id=None, parent_span_id=None, tracing=fake_tracing)
        [_ async for _ in emitter.yield_turn(turn)]
        assert fake_tracing.started == []
        assert fake_tracing.ended == []

    async def test_tracer_false_suppresses_spans(self) -> None:
        fake_tracing = FakeTracing()
        turn = CodexTurn(_aiter(_tool_then_text_events()), model="o4-mini")
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
