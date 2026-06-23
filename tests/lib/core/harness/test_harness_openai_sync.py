"""Integration test: sync (HTTP-yield) channel with an OpenAI-agents turn.

Exercises the unified harness surface (UnifiedEmitter.yield_turn + OpenAITurn)
with hand-built canonical StreamTaskMessage* streams so the test runs fully
offline (no API keys, no live OpenAI Agents run, no Agentex server).

Why an injected canonical stream
--------------------------------
OpenAI's native ``RunResultStreaming`` events are heavy SDK objects; the
``OpenAITurn`` accepts a pre-built canonical ``stream=`` of StreamTaskMessage*
events that bypasses ``convert_openai_to_agentex_events``. The shapes used here
are copied verbatim from the OpenAI converter contract exercised by
``tests/lib/core/harness/conformance/test_openai_conformance.py`` (tool calls
are Full(ToolRequestContent) + Full(ToolResponseContent); reasoning is
Start(ReasoningContent) + Delta + Done). This keeps the canonical stream
faithful to what the live converter produces while staying offline.

What is tested
--------------
- The sync handler forwards StreamTaskMessage* events verbatim in canonical
  order: tool_request (Full) -> tool_response (Full) -> text (Start+Delta+Done).
- Final accumulated text equals the seeded text deltas.
- With a trace_id + fake tracing, a tool span is opened (OpenSpan) on
  Full(ToolRequestContent) and closed (CloseSpan) on the matching
  Full(ToolResponseContent), and a reasoning span is opened/closed for a
  reasoning segment — proving the SpanDeriver is wired on the yield path.

What is NOT covered without live infrastructure
-----------------------------------------------
- Actual HTTP streaming over the ACP sync endpoint.
- A real ``Runner.run_streamed`` execution / live OpenAI model behaviour.
- ``convert_openai_to_agentex_events`` over real SDK events (covered by the
  OpenAI turn + conformance suites).

See also: test_harness_openai_async.py and test_harness_openai_temporal.py.
"""

from __future__ import annotations

from typing import Any, override

from agentex.types.text_delta import TextDelta
from agentex.types.text_content import TextContent
from tests.lib.core.harness._fakes import FakeTracing
from agentex.lib.core.harness.types import OpenSpan, CloseSpan, StreamTaskMessage
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.types.reasoning_content import ReasoningContent
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
from agentex.types.reasoning_content_delta import ReasoningContentDelta

# ---------------------------------------------------------------------------
# Canonical event fixtures (copied from the OpenAI converter contract)
# ---------------------------------------------------------------------------


def _tool_then_text_events() -> list[StreamTaskMessage]:
    """A tool round-trip followed by a final text reply.

    Mirrors the OpenAI converter's tool path: a Full(ToolRequestContent) for the
    call and a Full(ToolResponseContent) for the result (matched by tool_call_id),
    then a streamed text answer.
    """
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


def _reasoning_events() -> list[StreamTaskMessage]:
    """A reasoning segment: Start(ReasoningContent) + Delta + Done."""
    return [
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=ReasoningContent(type="reasoning", author="agent", summary=["Thinking..."]),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=ReasoningContentDelta(type="reasoning_content", content_index=0, content_delta="step 1"),
        ),
        StreamTaskMessageDone(type="done", index=0),
    ]


async def _canonical_stream(events: list[StreamTaskMessage]):
    for e in events:
        yield e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_yield_turn(
    events: list[StreamTaskMessage],
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    fake_tracing: FakeTracing | None = None,
) -> list[Any]:
    """Drive the sync (yield) path and collect all yielded events."""
    tracer: SpanTracer | bool | None = None
    if trace_id and fake_tracing is not None:
        tracer = SpanTracer(
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            task_id="task1",
            tracing=fake_tracing,
        )

    turn = OpenAITurn(stream=_canonical_stream(events), model="gpt-4o")
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

    async def test_tool_response_carries_weather_result(self) -> None:
        events = await _run_yield_turn(_tool_then_text_events())
        full_responses = [
            ev
            for ev in events
            if isinstance(ev, StreamTaskMessageFull) and isinstance(getattr(ev, "content", None), ToolResponseContent)
        ]
        assert len(full_responses) == 1
        tool_response = full_responses[0].content
        assert isinstance(tool_response, ToolResponseContent)
        assert "72F" in str(tool_response.content)
        assert tool_response.name == "get_weather"

    async def test_accumulated_text_matches_deltas(self) -> None:
        events = await _run_yield_turn(_tool_then_text_events())
        accumulated = "".join(
            ev.delta.text_delta
            for ev in events
            if isinstance(ev, StreamTaskMessageDelta) and isinstance(ev.delta, TextDelta) and ev.delta.text_delta
        )
        assert accumulated == "Sunny and 72F."

    async def test_every_start_has_matching_done(self) -> None:
        events = await _run_yield_turn(_tool_then_text_events())
        starts = {ev.index for ev in events if isinstance(ev, StreamTaskMessageStart)}
        dones = {ev.index for ev in events if isinstance(ev, StreamTaskMessageDone)}
        assert starts == dones, f"Unmatched Start/Done indices: starts={starts} dones={dones}"


# ---------------------------------------------------------------------------
# Tests: span derivation on the yield path
# ---------------------------------------------------------------------------


class TestSyncYieldSpanDerivation:
    async def test_tool_span_opened_and_closed(self) -> None:
        """Full(ToolRequestContent) opens a tool span; Full(ToolResponseContent) closes it."""
        fake_tracing = FakeTracing()
        await _run_yield_turn(
            _tool_then_text_events(),
            trace_id="trace1",
            parent_span_id="parent-span",
            fake_tracing=fake_tracing,
        )

        assert len(fake_tracing.started) == 1, "Expected exactly one tool span opened"
        assert len(fake_tracing.ended) == 1, "Expected exactly one tool span closed"
        name, parent_id, _ = fake_tracing.started[0]
        assert name == "get_weather"
        assert parent_id == "parent-span"

    async def test_tool_span_output_is_tool_result(self) -> None:
        fake_tracing = FakeTracing()
        await _run_yield_turn(
            _tool_then_text_events(),
            trace_id="trace1",
            parent_span_id="parent-span",
            fake_tracing=fake_tracing,
        )
        name, output = fake_tracing.ended[0]
        assert name == "get_weather"
        assert "72F" in str(output)

    async def test_reasoning_span_opened_and_closed(self) -> None:
        """A reasoning segment opens and closes a reasoning span."""
        fake_tracing = FakeTracing()
        await _run_yield_turn(
            _reasoning_events(),
            trace_id="trace1",
            parent_span_id="parent-span",
            fake_tracing=fake_tracing,
        )
        assert fake_tracing.started_names == ["reasoning"]
        assert len(fake_tracing.ended) == 1

    async def test_no_trace_id_means_no_spans(self) -> None:
        fake_tracing = FakeTracing()
        turn = OpenAITurn(stream=_canonical_stream(_tool_then_text_events()), model="gpt-4o")
        emitter = UnifiedEmitter(
            task_id="task1",
            trace_id=None,
            parent_span_id=None,
            tracing=fake_tracing,
        )
        [_ async for _ in emitter.yield_turn(turn)]
        assert fake_tracing.started == []
        assert fake_tracing.ended == []

    async def test_tracer_false_suppresses_spans(self) -> None:
        fake_tracing = FakeTracing()
        turn = OpenAITurn(stream=_canonical_stream(_tool_then_text_events()), model="gpt-4o")
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
        """The signals received by the tracer are OpenSpan then CloseSpan."""
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
        turn = OpenAITurn(stream=_canonical_stream(_tool_then_text_events()), model="gpt-4o")
        emitter = UnifiedEmitter(
            task_id="task1",
            trace_id="trace1",
            parent_span_id="parent",
            tracer=tracer,
        )
        [_ async for _ in emitter.yield_turn(turn)]

        assert len(received_signals) == 2
        assert isinstance(received_signals[0], OpenSpan)
        assert isinstance(received_signals[1], CloseSpan)
        assert received_signals[0].name == "get_weather"
