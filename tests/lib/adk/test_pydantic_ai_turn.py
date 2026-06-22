"""Tests for PydanticAITurn and pydantic_ai_usage_to_turn_usage."""

from __future__ import annotations

from typing import Any, AsyncIterator

from pydantic_ai.run import AgentRunResult, AgentRunResultEvent
from pydantic_ai.usage import RunUsage
from pydantic_ai.messages import (
    TextPart,
    PartEndEvent,
    TextPartDelta,
    PartDeltaEvent,
    PartStartEvent,
)

from agentex.lib.core.harness import HarnessTurn
from agentex.lib.adk._modules._pydantic_ai_turn import (
    PydanticAITurn,
    pydantic_ai_usage_to_turn_usage,
)


async def _aiter(events: list[Any]) -> AsyncIterator[Any]:
    for e in events:
        yield e


async def _collect(stream: AsyncIterator[Any]) -> list[Any]:
    return [e async for e in stream]


def _make_result_event(output: Any = "done", usage: RunUsage | None = None) -> AgentRunResultEvent:
    result = AgentRunResult(output=output, _output_tool_name=None)
    if usage is not None:
        result._state.usage = usage
    return AgentRunResultEvent(result=result)


class TestUsageNormalization:
    def test_usage_normalization_maps_fields(self):
        """Real RunUsage fields map correctly onto TurnUsage."""
        usage = RunUsage(
            requests=3,
            input_tokens=200,
            output_tokens=80,
            cache_read_tokens=25,
        )
        turn_usage = pydantic_ai_usage_to_turn_usage(usage, model="openai:gpt-4o")

        assert turn_usage.model == "openai:gpt-4o"
        assert turn_usage.input_tokens == 200
        assert turn_usage.output_tokens == 80
        assert turn_usage.num_llm_calls == 3

    def test_total_tokens_is_computed(self):
        """RunUsage.total_tokens is a computed property; we surface it correctly."""
        usage = RunUsage(input_tokens=100, output_tokens=50)
        turn_usage = pydantic_ai_usage_to_turn_usage(usage, model="openai:gpt-4o")
        assert turn_usage.total_tokens == 150

    def test_cache_read_tokens_mapped_to_cached_input_tokens(self):
        usage = RunUsage(input_tokens=100, output_tokens=50, cache_read_tokens=20)
        turn_usage = pydantic_ai_usage_to_turn_usage(usage, model="openai:gpt-4o")
        assert turn_usage.cached_input_tokens == 20

    def test_none_model(self):
        """model=None is preserved."""
        usage = RunUsage()
        turn_usage = pydantic_ai_usage_to_turn_usage(usage, model=None)
        assert turn_usage.model is None

    def test_all_zero_usage_preserves_real_zeros(self):
        """An all-zero RunUsage maps real 0s through (not None).

        RunUsage token fields are ints defaulting to 0. A 0 is a genuine
        value (e.g. a cache-hit with 0 output tokens), not "unknown", so it
        must survive normalization as 0 rather than being coerced to None.
        """
        usage = RunUsage()
        turn_usage = pydantic_ai_usage_to_turn_usage(usage, model="openai:gpt-4o")
        assert turn_usage.num_llm_calls == 0
        assert turn_usage.input_tokens == 0
        assert turn_usage.output_tokens == 0
        assert turn_usage.cached_input_tokens == 0
        assert turn_usage.total_tokens == 0

    def test_missing_field_degrades_to_none(self):
        """A usage object MISSING a field maps that field to None (defensive getattr).

        Guards the version-rename guarantee: if pydantic-ai renames a field,
        the absent attribute degrades to None rather than raising.
        """

        class StubUsage:
            requests = 2
            input_tokens = 100
            # no output_tokens / cache_read_tokens / total_tokens attributes

        turn_usage = pydantic_ai_usage_to_turn_usage(StubUsage(), model="openai:gpt-4o")
        assert turn_usage.num_llm_calls == 2
        assert turn_usage.input_tokens == 100
        assert turn_usage.output_tokens is None
        assert turn_usage.cached_input_tokens is None
        assert turn_usage.total_tokens is None


class TestPydanticAITurn:
    async def test_turn_satisfies_harness_turn_protocol(self):
        """PydanticAITurn is structurally compatible with HarnessTurn."""
        turn = PydanticAITurn(_aiter([]), model="openai:gpt-4o")
        assert isinstance(turn, HarnessTurn)

    async def test_usage_before_exhaustion_returns_default(self):
        """usage() before iterating events returns default TurnUsage (model set, tokens None)."""
        result_event = _make_result_event(usage=RunUsage(requests=1, input_tokens=100, output_tokens=40))
        events = [result_event]
        turn = PydanticAITurn(_aiter(events), model="openai:gpt-4o")

        # Do NOT exhaust events — check usage pre-run
        pre_usage = turn.usage()
        assert pre_usage.model == "openai:gpt-4o"
        assert pre_usage.input_tokens is None
        assert pre_usage.output_tokens is None
        assert pre_usage.num_llm_calls is None

    async def test_turn_events_and_usage(self):
        """Driving events to exhaustion populates usage from the terminal event."""
        known_usage = RunUsage(
            requests=2,
            input_tokens=300,
            output_tokens=120,
            cache_read_tokens=30,
        )
        result_event = _make_result_event(usage=known_usage)
        events = [
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="hi")),
            PartEndEvent(index=0, part=TextPart(content="hi")),
            result_event,
        ]
        turn = PydanticAITurn(_aiter(events), model="openai:gpt-4o")

        collected = await _collect(turn.events)

        # Events match bare converter output (Start + Delta + Done = 3 events)
        assert len(collected) == 3

        # Usage is populated after exhaustion
        usage = turn.usage()
        assert usage.model == "openai:gpt-4o"
        assert usage.input_tokens == 300
        assert usage.output_tokens == 120
        assert usage.cached_input_tokens == 30
        assert usage.num_llm_calls == 2
        assert usage.total_tokens == 420

    async def test_events_match_bare_converter(self):
        """Yielded events are identical to bare convert_pydantic_ai_to_agentex_events output."""
        from agentex.lib.adk._modules._pydantic_ai_sync import convert_pydantic_ai_to_agentex_events

        text_events = [
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Hello")),
            PartEndEvent(index=0, part=TextPart(content="Hello")),
        ]

        turn = PydanticAITurn(_aiter(text_events), model="openai:gpt-4o")
        turn_out = await _collect(turn.events)

        bare_out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(text_events)))

        assert len(turn_out) == len(bare_out)
        for a, b in zip(turn_out, bare_out):
            assert type(a) is type(b)
            assert a.model_dump() == b.model_dump()

    async def test_usage_captured_via_real_usage_accessor(self):
        """Drive the turn through the REAL ``result.usage`` property accessor.

        The production code reads ``getattr(run_result, "usage", None)``, which
        on this pydantic-ai version resolves the ``_DeprecatedCallableRunUsage``
        property (NOT ``_state.usage`` directly). This asserts that the real
        accessor path the converter uses captures the run usage. Constructing
        the event without our test's ``_state`` shortcut: we set ``_state.usage``
        only because that is the sole supported way to seed an
        ``AgentRunResult``, but we then assert capture happens through the
        public ``.usage`` attribute access (verified below).
        """
        known_usage = RunUsage(requests=4, input_tokens=512, output_tokens=64)
        result = AgentRunResult(output="done", _output_tool_name=None)
        result._state.usage = known_usage
        result_event = AgentRunResultEvent(result=result)

        # Sanity: the value is reachable via the real public accessor the
        # production code uses (not just via the private _state). The
        # _DeprecatedCallableRunUsage property wraps the value, so compare by
        # equality rather than identity.
        accessed = getattr(result_event.result, "usage", None)
        assert accessed is not None
        assert accessed.input_tokens == 512
        assert accessed.requests == 4

        events = [
            PartStartEvent(index=0, part=TextPart(content="")),
            PartEndEvent(index=0, part=TextPart(content="")),
            result_event,
        ]
        turn = PydanticAITurn(_aiter(events), model="anthropic:claude-3-5-sonnet")
        await _collect(turn.events)

        usage = turn.usage()
        assert usage.model == "anthropic:claude-3-5-sonnet"
        assert usage.input_tokens == 512
        assert usage.output_tokens == 64
        assert usage.num_llm_calls == 4

    async def test_no_usage_event_leaves_default_usage(self):
        """If the stream has no AgentRunResultEvent, usage() returns the default (tokens None)."""
        events = [
            PartStartEvent(index=0, part=TextPart(content="")),
            PartEndEvent(index=0, part=TextPart(content="")),
        ]
        turn = PydanticAITurn(_aiter(events), model="openai:gpt-4o")
        await _collect(turn.events)

        usage = turn.usage()
        assert usage.model == "openai:gpt-4o"
        assert usage.input_tokens is None
        assert usage.num_llm_calls is None


class TestToolRequestStreaming:
    """PydanticAITurn.events equals the bare converter output unconditionally.

    The foundation auto_send delivers Start+ToolRequestDelta+Done natively, so
    no coalescing is needed on either channel.
    """

    async def test_events_match_bare_converter_for_streamed_tool_call(self):
        """PydanticAITurn yields a ToolRequestDelta for a streamed-args tool call
        — i.e. it is byte-for-byte the bare converter output, preserving
        argument-token streaming on the sync/yield channel."""
        from pydantic_ai.messages import ToolCallPart, ToolCallPartDelta

        from agentex.types.tool_request_delta import ToolRequestDelta
        from agentex.types.task_message_update import StreamTaskMessageDelta
        from agentex.lib.adk._modules._pydantic_ai_sync import convert_pydantic_ai_to_agentex_events

        tool_events = [
            PartStartEvent(index=0, part=ToolCallPart(tool_name="get_weather", args=None, tool_call_id="c1")),
            PartDeltaEvent(index=0, delta=ToolCallPartDelta(args_delta='{"city":"Paris"}')),
            PartEndEvent(
                index=0,
                part=ToolCallPart(tool_name="get_weather", args='{"city":"Paris"}', tool_call_id="c1"),
            ),
        ]

        turn = PydanticAITurn(_aiter(tool_events), model="openai:gpt-4o")
        turn_out = await _collect(turn.events)

        bare_out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(tool_events)))

        # Turn is identical to the bare converter.
        assert len(turn_out) == len(bare_out)
        for a, b in zip(turn_out, bare_out):
            assert type(a) is type(b)
            assert a.model_dump() == b.model_dump()

        # The arg-streaming delta is present.
        deltas = [
            e for e in turn_out if isinstance(e, StreamTaskMessageDelta) and isinstance(e.delta, ToolRequestDelta)
        ]
        assert len(deltas) == 1, "streamed tool-call args must surface as a ToolRequestDelta"
        assert isinstance(deltas[0].delta, ToolRequestDelta)
        assert deltas[0].delta.arguments_delta == '{"city":"Paris"}'
