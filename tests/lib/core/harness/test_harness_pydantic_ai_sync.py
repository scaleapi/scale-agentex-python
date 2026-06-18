"""Integration test: sync (HTTP-yield) channel with a pydantic-ai agent.

Exercises the unified harness surface (UnifiedEmitter.yield_turn + PydanticAITurn)
with a minimal pydantic-ai agent backed by TestModel so the test runs fully
offline (no API keys, no live infrastructure).

Agent description
-----------------
A single-tool agent with ``get_weather(city: str) -> str`` that always returns
"sunny and 72F". TestModel is configured to call that tool once then produce
a fixed text reply, giving a deterministic event sequence.

What is tested
--------------
- The sync handler correctly yields StreamTaskMessage* events in order:
  tool_request (Start+Done) then tool_response (Full) then text (Start+Delta+Done).
- Final accumulated text equals the TestModel custom output.
- With a trace_id + fake tracing, a tool span is opened (OpenSpan) and
  closed (CloseSpan) — proving the SpanDeriver is wired on the yield path.

What is NOT covered without live infrastructure
-----------------------------------------------
- Actual HTTP streaming over the ACP sync endpoint (requires a running
  Agentex server + deployed agent).
- Real LLM calls or production model behaviour.
- The full FastACP request/response lifecycle.

See also: tests/lib/core/harness/test_harness_pydantic_ai_async.py and
test_harness_pydantic_ai_temporal.py for the other two channels.
"""

from __future__ import annotations

from typing import Any, override

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agentex.types.text_delta import TextDelta
from agentex.lib.core.harness.types import OpenSpan, CloseSpan
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageStart,
)
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._pydantic_ai_turn import PydanticAITurn

# ---------------------------------------------------------------------------
# Minimal agent under test
# ---------------------------------------------------------------------------


def _make_agent() -> Agent:
    """Build a pydantic-ai agent with one weather tool and a TestModel.

    TestModel is instantiated with call_tools=['get_weather'] so it always
    invokes the tool once, then emits custom_output_text as the reply.
    """
    model = TestModel(
        call_tools=["get_weather"],
        custom_output_text="The weather in Paris is sunny and 72F.",
    )
    agent: Agent = Agent(model)

    @agent.tool_plain
    def get_weather(city: str) -> str:
        """Get the current weather for a city."""
        return f"The weather in {city} is sunny and 72F"

    return agent


# ---------------------------------------------------------------------------
# Fake tracing backend (no network calls)
# ---------------------------------------------------------------------------


class _FakeSpan:
    def __init__(self, name: str) -> None:
        self.name = name
        self.output: Any = None


class _FakeTracing:
    def __init__(self) -> None:
        self.started: list[tuple[str, str | None]] = []
        self.ended: list[tuple[str, Any]] = []

    async def start_span(
        self,
        *,
        trace_id: str,
        name: str,
        input: Any = None,
        parent_id: Any = None,
        data: Any = None,
        task_id: Any = None,
    ) -> _FakeSpan:
        self.started.append((name, parent_id))
        return _FakeSpan(name)

    async def end_span(self, *, trace_id: str, span: _FakeSpan) -> None:
        self.ended.append((span.name, span.output))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_yield_turn(
    agent: Agent,
    user_msg: str = "What is the weather in Paris?",
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    fake_tracing: _FakeTracing | None = None,
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

    events: list[Any] = []
    async with agent.run_stream_events(user_msg) as stream:
        turn = PydanticAITurn(stream, model="test")
        emitter = UnifiedEmitter(
            task_id="task1",
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            tracer=tracer if tracer is not None else False,
        )
        events = [ev async for ev in emitter.yield_turn(turn)]
    return events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSyncYieldEventOrder:
    """The yield channel forwards events in canonical order."""

    async def test_tool_request_precedes_tool_response(self) -> None:
        """tool_request events appear before the tool_response Full event."""
        agent = _make_agent()
        events = await _run_yield_turn(agent)

        content_types = [
            getattr(getattr(ev, "content", None), "type", None)
            for ev in events
            if isinstance(ev, (StreamTaskMessageStart, StreamTaskMessageFull))
        ]
        assert "tool_request" in content_types
        assert "tool_response" in content_types
        tool_req_idx = content_types.index("tool_request")
        tool_resp_idx = content_types.index("tool_response")
        assert tool_req_idx < tool_resp_idx, "tool_request must appear before tool_response in the event stream"

    async def test_text_appears_after_tool_response(self) -> None:
        """Text content (Start/Done) comes after the tool_response Full event."""
        agent = _make_agent()
        events = await _run_yield_turn(agent)

        full_types = [
            getattr(getattr(ev, "content", None), "type", None)
            for ev in events
            if isinstance(ev, StreamTaskMessageFull)
        ]
        start_types = [
            getattr(getattr(ev, "content", None), "type", None)
            for ev in events
            if isinstance(ev, StreamTaskMessageStart)
        ]

        assert "tool_response" in full_types
        assert "text" in start_types

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
        """The ToolResponseContent contains the get_weather return value."""
        agent = _make_agent()
        events = await _run_yield_turn(agent)

        full_events = [
            ev
            for ev in events
            if isinstance(ev, StreamTaskMessageFull) and isinstance(getattr(ev, "content", None), ToolResponseContent)
        ]
        assert len(full_events) >= 1, "Expected at least one tool_response Full event"
        tool_response = full_events[0].content
        assert isinstance(tool_response, ToolResponseContent)
        assert isinstance(tool_response.content, str)
        assert "72F" in tool_response.content
        assert tool_response.name == "get_weather"

    async def test_accumulated_text_matches_model_output(self) -> None:
        """Accumulated text deltas equal the TestModel custom_output_text."""
        from agentex.types.task_message_update import StreamTaskMessageDelta

        agent = _make_agent()
        events = await _run_yield_turn(agent)

        accumulated = "".join(
            ev.delta.text_delta
            for ev in events
            if isinstance(ev, StreamTaskMessageDelta) and isinstance(ev.delta, TextDelta) and ev.delta.text_delta
        )
        assert accumulated == "The weather in Paris is sunny and 72F."

    async def test_every_start_has_matching_done(self) -> None:
        """Every StreamTaskMessageStart has a corresponding StreamTaskMessageDone."""
        agent = _make_agent()
        events = await _run_yield_turn(agent)

        starts = {ev.index for ev in events if isinstance(ev, StreamTaskMessageStart)}
        dones = {ev.index for ev in events if isinstance(ev, StreamTaskMessageDone)}
        assert starts == dones, f"Unmatched Start/Done indices: starts={starts} dones={dones}"


class TestSyncYieldSpanDerivation:
    """SpanDeriver is wired on the yield path; tool spans are opened/closed."""

    async def test_tool_span_opened_and_closed(self) -> None:
        """One tool span is opened and closed per tool call."""
        agent = _make_agent()
        fake_tracing = _FakeTracing()
        tracer = SpanTracer(
            trace_id="trace1",
            parent_span_id="parent-span",
            task_id="task1",
            tracing=fake_tracing,
        )

        async with agent.run_stream_events("What is the weather in Paris?") as stream:
            turn = PydanticAITurn(stream, model="test")
            emitter = UnifiedEmitter(
                task_id="task1",
                trace_id="trace1",
                parent_span_id="parent-span",
                tracer=tracer,
            )
            await emitter.yield_turn(turn).__anext__.__self__ if False else None
            [_ async for _ in emitter.yield_turn(turn)]

        assert len(fake_tracing.started) == 1, "Expected exactly one tool span opened"
        assert len(fake_tracing.ended) == 1, "Expected exactly one tool span closed"
        span_name, parent_id = fake_tracing.started[0]
        assert span_name == "get_weather"
        assert parent_id == "parent-span"

    async def test_tool_span_output_is_tool_result(self) -> None:
        """The closed tool span's output equals the tool's return value."""
        agent = _make_agent()
        fake_tracing = _FakeTracing()
        tracer = SpanTracer(
            trace_id="trace1",
            parent_span_id="parent-span",
            task_id="task1",
            tracing=fake_tracing,
        )

        async with agent.run_stream_events("What is the weather in Paris?") as stream:
            turn = PydanticAITurn(stream, model="test")
            emitter = UnifiedEmitter(
                task_id="task1",
                trace_id="trace1",
                parent_span_id="parent-span",
                tracer=tracer,
            )
            [_ async for _ in emitter.yield_turn(turn)]

        name, output = fake_tracing.ended[0]
        assert name == "get_weather"
        assert output is not None
        assert "72F" in str(output)

    async def test_no_trace_id_means_no_spans(self) -> None:
        """With trace_id=None, no spans are derived (emitter disables tracing)."""
        agent = _make_agent()
        fake_tracing = _FakeTracing()

        async with agent.run_stream_events("What is the weather in Paris?") as stream:
            turn = PydanticAITurn(stream, model="test")
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
        """tracer=False disables span derivation regardless of trace_id."""
        agent = _make_agent()
        fake_tracing = _FakeTracing()

        async with agent.run_stream_events("What is the weather in Paris?") as stream:
            turn = PydanticAITurn(stream, model="test")
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
        from agentex.lib.core.harness.tracer import SpanTracer as RealTracer

        received_signals: list[Any] = []

        class _RecordingTracer(RealTracer):
            @override
            async def handle(self, signal: Any) -> None:
                received_signals.append(signal)
                await super().handle(signal)

        fake_tracing = _FakeTracing()
        tracer = _RecordingTracer(
            trace_id="trace1",
            parent_span_id="parent",
            task_id="task1",
            tracing=fake_tracing,
        )

        agent = _make_agent()
        async with agent.run_stream_events("What is the weather in Paris?") as stream:
            turn = PydanticAITurn(stream, model="test")
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


@pytest.mark.parametrize(
    "user_msg",
    [
        "What is the weather in Paris?",
        "Tell me the weather in London.",
    ],
)
async def test_sync_handler_produces_events_for_various_inputs(user_msg: str) -> None:
    """Yield path produces at least a tool_response Full for any user message."""
    agent = _make_agent()
    events = await _run_yield_turn(agent, user_msg=user_msg)

    full_event_types = [
        getattr(getattr(ev, "content", None), "type", None) for ev in events if isinstance(ev, StreamTaskMessageFull)
    ]
    assert "tool_response" in full_event_types
