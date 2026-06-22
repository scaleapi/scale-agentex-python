"""Tests for the unified sync (HTTP ACP) path: PydanticAITurn + UnifiedEmitter.

Exercises the path documented in _pydantic_ai_sync.py under "Recommended: unified surface":
- events forwarded by yield_turn equal PydanticAITurn(stream).events (passthrough)
- with a trace context + fake tracing backend, tool spans are derived (start_span / end_span called)
- with a trace context + fake tracing backend, reasoning spans are derived
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from pydantic_ai.run import AgentRunResult, AgentRunResultEvent
from pydantic_ai.usage import RunUsage
from pydantic_ai.messages import (
    TextPart,
    PartEndEvent,
    ThinkingPart,
    ToolCallPart,
    TextPartDelta,
    PartDeltaEvent,
    PartStartEvent,
    ThinkingPartDelta,
    ToolCallPartDelta,
)

from agentex.lib.core.harness import UnifiedEmitter
from tests.lib.core.harness._fakes import FakeTracing
from agentex.lib.adk._modules._pydantic_ai_turn import PydanticAITurn


async def _aiter(events: list[Any]) -> AsyncIterator[Any]:
    for e in events:
        yield e


async def _collect(stream: AsyncIterator[Any]) -> list[Any]:
    return [e async for e in stream]


def _make_result_event(usage: RunUsage | None = None) -> AgentRunResultEvent:
    result = AgentRunResult(output="done", _output_tool_name=None)
    if usage is not None:
        result._state.usage = usage
    return AgentRunResultEvent(result=result)


class TestUnifiedSyncPathPassthrough:
    """The events forwarded by yield_turn are identical to PydanticAITurn.events."""

    async def test_text_stream_passthrough(self):
        raw_events = [
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="hello")),
            PartEndEvent(index=0, part=TextPart(content="hello")),
        ]

        turn_a = PydanticAITurn(_aiter(raw_events), model="openai:gpt-4o")
        direct = await _collect(turn_a.events)

        turn_b = PydanticAITurn(_aiter(raw_events), model="openai:gpt-4o")
        emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None)
        via_emitter = await _collect(emitter.yield_turn(turn_b))

        assert len(via_emitter) == len(direct)
        for a, b in zip(via_emitter, direct):
            assert type(a) is type(b)
            assert a.model_dump() == b.model_dump()

    async def test_tool_call_stream_passthrough(self):
        raw_events = [
            PartStartEvent(index=0, part=ToolCallPart(tool_name="Bash", args=None, tool_call_id="c1")),
            PartDeltaEvent(index=0, delta=ToolCallPartDelta(args_delta='{"cmd":"ls"}')),
            PartEndEvent(
                index=0,
                part=ToolCallPart(tool_name="Bash", args='{"cmd":"ls"}', tool_call_id="c1"),
            ),
        ]

        turn_a = PydanticAITurn(_aiter(raw_events), model="openai:gpt-4o")
        direct = await _collect(turn_a.events)

        turn_b = PydanticAITurn(_aiter(raw_events), model="openai:gpt-4o")
        emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None)
        via_emitter = await _collect(emitter.yield_turn(turn_b))

        assert len(via_emitter) == len(direct)
        for a, b in zip(via_emitter, direct):
            assert type(a) is type(b)
            assert a.model_dump() == b.model_dump()


class TestUnifiedSyncPathSpanDerivation:
    """With trace context + fake tracing, spans are derived from the stream."""

    async def test_tool_span_opened_and_closed(self):
        """A tool call produces start_span + end_span on the fake tracing backend."""
        from pydantic_ai.messages import ToolReturnPart, FunctionToolResultEvent

        tool_events = [
            PartStartEvent(
                index=0,
                part=ToolCallPart(tool_name="Bash", args={"cmd": "ls"}, tool_call_id="call_1"),
            ),
            PartEndEvent(
                index=0,
                part=ToolCallPart(tool_name="Bash", args='{"cmd":"ls"}', tool_call_id="call_1"),
            ),
            FunctionToolResultEvent(
                part=ToolReturnPart(tool_name="Bash", content="files", tool_call_id="call_1"),
            ),
        ]

        fake = FakeTracing()
        turn = PydanticAITurn(_aiter(tool_events), model="openai:gpt-4o")
        emitter = UnifiedEmitter(task_id="t", trace_id="tr", parent_span_id="p", tracing=fake)

        events = await _collect(emitter.yield_turn(turn))

        assert len(events) >= 2, "at least Start(tool) + Done + Full(response)"
        assert len(fake.started) == 1, "one tool span opened"
        assert len(fake.ended) == 1, "one tool span closed"
        span_name, parent_id, span_input = fake.started[0]
        assert span_name == "Bash"
        assert parent_id == "p"
        closed_name, closed_output = fake.ended[0]
        assert closed_name == "Bash"

    async def test_reasoning_span_opened_and_closed(self):
        """A thinking/reasoning block produces start_span + end_span."""
        reasoning_events = [
            PartStartEvent(index=0, part=ThinkingPart(content="")),
            PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta="let me think")),
            PartEndEvent(index=0, part=ThinkingPart(content="let me think")),
        ]

        fake = FakeTracing()
        turn = PydanticAITurn(_aiter(reasoning_events), model="openai:gpt-4o")
        emitter = UnifiedEmitter(task_id="t", trace_id="tr", parent_span_id="p", tracing=fake)

        await _collect(emitter.yield_turn(turn))

        assert len(fake.started) == 1, "one reasoning span opened"
        assert len(fake.ended) == 1, "one reasoning span closed"
        span_name, parent_id, _ = fake.started[0]
        assert span_name == "reasoning"
        assert parent_id == "p"

    async def test_no_trace_id_means_no_spans(self):
        """When trace_id is None, no spans are derived even with a fake tracing backend."""
        raw_events = [
            PartStartEvent(
                index=0,
                part=ToolCallPart(tool_name="Bash", args={"cmd": "ls"}, tool_call_id="c2"),
            ),
            PartEndEvent(
                index=0,
                part=ToolCallPart(tool_name="Bash", args='{"cmd":"ls"}', tool_call_id="c2"),
            ),
        ]

        fake = FakeTracing()
        turn = PydanticAITurn(_aiter(raw_events), model="openai:gpt-4o")
        emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None, tracing=fake)

        await _collect(emitter.yield_turn(turn))

        assert fake.started == [], "no spans when trace_id is absent"
        assert fake.ended == []

    async def test_tracer_false_suppresses_spans_even_with_trace_id(self):
        """tracer=False disables span derivation regardless of trace_id."""
        raw_events = [
            PartStartEvent(
                index=0,
                part=ToolCallPart(tool_name="Bash", args={"cmd": "ls"}, tool_call_id="c3"),
            ),
            PartEndEvent(
                index=0,
                part=ToolCallPart(tool_name="Bash", args='{"cmd":"ls"}', tool_call_id="c3"),
            ),
        ]

        fake = FakeTracing()
        turn = PydanticAITurn(_aiter(raw_events), model="openai:gpt-4o")
        emitter = UnifiedEmitter(task_id="t", trace_id="tr", parent_span_id="p", tracer=False, tracing=fake)

        await _collect(emitter.yield_turn(turn))

        assert fake.started == []
        assert fake.ended == []
