"""Tests for the sync Pydantic AI -> Agentex path.

Covers:
- The bare converter ``convert_pydantic_ai_to_agentex_events`` (text/thinking/
  tool-call streaming and arg-delta handling).
- The unified sync (HTTP ACP) path ``UnifiedEmitter.yield_turn(PydanticAITurn(...))``:
    * Passthrough: yield_turn events equal PydanticAITurn(stream).events
    * Span derivation (tool + reasoning) with a fake tracing backend
"""

from __future__ import annotations

import json
import asyncio
from typing import Any, AsyncIterator

import pytest
from pydantic_ai.run import AgentRunResult, AgentRunResultEvent
from pydantic_ai.messages import (
    TextPart,
    PartEndEvent,
    ThinkingPart,
    ToolCallPart,
    TextPartDelta,
    PartDeltaEvent,
    PartStartEvent,
    ToolReturnPart,
    RetryPromptPart,
    FinalResultEvent,
    ThinkingPartDelta,
    ToolCallPartDelta,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
)

from agentex.lib.core.harness import UnifiedEmitter
from tests.lib.core.harness._fakes import FakeTracing
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.tool_request_delta import ToolRequestDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.task_message_content import TextContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.types.reasoning_content_delta import ReasoningContentDelta
from agentex.lib.adk._modules._pydantic_ai_sync import (
    _args_delta_to_str,
    convert_pydantic_ai_to_agentex_events,
)
from agentex.lib.adk._modules._pydantic_ai_turn import PydanticAITurn


async def _aiter(events: list[Any]) -> AsyncIterator[Any]:
    for e in events:
        yield e


async def _collect(stream: AsyncIterator[Any]) -> list[Any]:
    return [e async for e in stream]


class TestArgsDeltaToStr:
    def test_none(self):
        assert _args_delta_to_str(None) == ""

    def test_string_passthrough(self):
        assert _args_delta_to_str('{"k":') == '{"k":'

    def test_dict_dumps_json(self):
        assert json.loads(_args_delta_to_str({"city": "Paris"})) == {"city": "Paris"}


class TestTextStreaming:
    async def test_plain_text_emits_start_deltas_done(self):
        events = [
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Hello")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta=", ")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="world!")),
            PartEndEvent(index=0, part=TextPart(content="Hello, world!")),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))

        assert len(out) == 5
        assert isinstance(out[0], StreamTaskMessageStart)
        assert isinstance(out[0].content, TextContent)
        assert out[0].content.content == ""
        assert out[0].index == 0

        for i, expected in enumerate(["Hello", ", ", "world!"], start=1):
            assert isinstance(out[i], StreamTaskMessageDelta)
            assert isinstance(out[i].delta, TextDelta)
            assert out[i].delta.text_delta == expected
            assert out[i].index == 0

        assert isinstance(out[4], StreamTaskMessageDone)
        assert out[4].index == 0

    async def test_text_with_initial_content_emits_delta(self):
        """Pydantic AI puts the first streaming chunk in PartStartEvent.part.content.

        The Agentex protocol only renders Delta events as the message body, so we
        must emit the initial content as a Delta — not in the Start — otherwise
        the first chunk disappears from the visible message.
        """
        events = [
            PartStartEvent(index=0, part=TextPart(content="Already there")),
            PartEndEvent(index=0, part=TextPart(content="Already there")),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))
        assert isinstance(out[0], StreamTaskMessageStart)
        assert isinstance(out[0].content, TextContent)
        assert out[0].content.content == ""
        assert isinstance(out[1], StreamTaskMessageDelta)
        assert isinstance(out[1].delta, TextDelta)
        assert out[1].delta.text_delta == "Already there"


class TestThinkingStreaming:
    async def test_thinking_emits_reasoning_deltas(self):
        events = [
            PartStartEvent(index=0, part=ThinkingPart(content="")),
            PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta="step 1...")),
            PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta=" step 2.")),
            PartEndEvent(index=0, part=ThinkingPart(content="step 1... step 2.")),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))

        assert isinstance(out[0], StreamTaskMessageStart)
        # Thinking content opens a ReasoningContent start, not a TextContent one,
        # so the Start's content_type matches the ReasoningContentDelta updates
        # that follow. Mismatched types here would render thinking as a plain
        # text bubble (or break server-side accumulators) instead of a
        # collapsible reasoning block.
        assert isinstance(out[0].content, ReasoningContent)
        assert isinstance(out[1], StreamTaskMessageDelta)
        assert isinstance(out[1].delta, ReasoningContentDelta)
        assert out[1].delta.content_delta == "step 1..."
        assert out[1].delta.content_index == 0
        assert isinstance(out[2].delta, ReasoningContentDelta)
        assert out[2].delta.content_delta == " step 2."
        assert isinstance(out[3], StreamTaskMessageDone)

    async def test_thinking_with_initial_content_emits_delta(self):
        events = [
            PartStartEvent(index=0, part=ThinkingPart(content="seed reasoning")),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))
        assert isinstance(out[0], StreamTaskMessageStart)
        assert isinstance(out[1], StreamTaskMessageDelta)
        assert isinstance(out[1].delta, ReasoningContentDelta)
        assert out[1].delta.content_delta == "seed reasoning"

    async def test_thinking_delta_skipped_when_empty(self):
        events = [
            PartStartEvent(index=0, part=ThinkingPart(content="")),
            PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta=None)),
            PartEndEvent(index=0, part=ThinkingPart(content="")),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))
        assert len(out) == 2  # Start + Done; no delta for None content


class TestToolCallStreaming:
    async def test_tool_call_streamed_token_by_token(self):
        """The headline use case: tool-call argument tokens streaming through to the client."""
        events = [
            PartStartEvent(
                index=1,
                part=ToolCallPart(tool_name="get_weather", args=None, tool_call_id="call_abc"),
            ),
            PartDeltaEvent(
                index=1,
                delta=ToolCallPartDelta(args_delta='{"city":', tool_call_id="call_abc"),
            ),
            PartDeltaEvent(index=1, delta=ToolCallPartDelta(args_delta='"Paris"}')),
            PartEndEvent(
                index=1,
                part=ToolCallPart(tool_name="get_weather", args='{"city":"Paris"}', tool_call_id="call_abc"),
            ),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))

        assert len(out) == 4
        assert isinstance(out[0], StreamTaskMessageStart)
        assert isinstance(out[0].content, ToolRequestContent)
        assert out[0].content.tool_call_id == "call_abc"
        assert out[0].content.name == "get_weather"
        assert out[0].content.arguments == {}

        assert isinstance(out[1].delta, ToolRequestDelta)
        assert out[1].delta.tool_call_id == "call_abc"
        assert out[1].delta.name == "get_weather"
        assert out[1].delta.arguments_delta == '{"city":'

        assert isinstance(out[2].delta, ToolRequestDelta)
        assert out[2].delta.arguments_delta == '"Paris"}'
        # tool_call_id is carried forward from the start even when the delta omits it
        assert out[2].delta.tool_call_id == "call_abc"

        assert isinstance(out[3], StreamTaskMessageDone)

    async def test_tool_call_with_full_args_at_start(self):
        """Some providers return a tool call in one shot — args dict is set at start."""
        events = [
            PartStartEvent(
                index=0,
                part=ToolCallPart(tool_name="search", args={"query": "weather"}, tool_call_id="call_xyz"),
            ),
            PartEndEvent(
                index=0,
                part=ToolCallPart(tool_name="search", args={"query": "weather"}, tool_call_id="call_xyz"),
            ),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))
        assert isinstance(out[0], StreamTaskMessageStart)
        assert isinstance(out[0].content, ToolRequestContent)
        assert out[0].content.arguments == {"query": "weather"}
        # No deltas emitted — args were already complete.
        assert len(out) == 2
        assert isinstance(out[1], StreamTaskMessageDone)

    async def test_tool_call_with_full_args_string_at_start(self):
        """When args is a complete JSON string at start, surface it as a single delta."""
        events = [
            PartStartEvent(
                index=0,
                part=ToolCallPart(tool_name="search", args='{"query":"weather"}', tool_call_id="call_z"),
            ),
            PartEndEvent(
                index=0,
                part=ToolCallPart(tool_name="search", args='{"query":"weather"}', tool_call_id="call_z"),
            ),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))
        assert isinstance(out[0], StreamTaskMessageStart)
        assert isinstance(out[0].content, ToolRequestContent)
        assert out[0].content.arguments == {}
        assert isinstance(out[1], StreamTaskMessageDelta)
        assert isinstance(out[1].delta, ToolRequestDelta)
        assert out[1].delta.arguments_delta == '{"query":"weather"}'

    async def test_tool_call_dict_args_delta_serialized(self):
        events = [
            PartStartEvent(
                index=0,
                part=ToolCallPart(tool_name="t", args=None, tool_call_id="cid"),
            ),
            PartDeltaEvent(
                index=0,
                delta=ToolCallPartDelta(args_delta={"k": "v"}, tool_call_id="cid"),
            ),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))
        assert json.loads(out[1].delta.arguments_delta) == {"k": "v"}

    async def test_tool_result_emits_full(self):
        events = [
            PartStartEvent(
                index=0,
                part=ToolCallPart(tool_name="get_weather", args=None, tool_call_id="call_abc"),
            ),
            PartEndEvent(
                index=0,
                part=ToolCallPart(tool_name="get_weather", args="{}", tool_call_id="call_abc"),
            ),
            FunctionToolResultEvent(
                part=ToolReturnPart(tool_name="get_weather", content="Sunny, 72F", tool_call_id="call_abc"),
            ),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))

        # Last event is the tool result -> Full ToolResponseContent
        assert isinstance(out[-1], StreamTaskMessageFull)
        assert isinstance(out[-1].content, ToolResponseContent)
        assert out[-1].content.tool_call_id == "call_abc"
        assert out[-1].content.name == "get_weather"
        assert out[-1].content.content == "Sunny, 72F"

    async def test_tool_retry_prompt_surfaces_as_response(self):
        events = [
            FunctionToolResultEvent(
                part=RetryPromptPart(
                    content="bad arguments",
                    tool_name="get_weather",
                    tool_call_id="call_abc",
                ),
            ),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))
        assert isinstance(out[0], StreamTaskMessageFull)
        assert isinstance(out[0].content, ToolResponseContent)
        assert out[0].content.tool_call_id == "call_abc"
        assert out[0].content.name == "get_weather"
        # RetryPromptPart's content is the error message
        assert out[0].content.content == "bad arguments"


class TestMultiStepRun:
    async def test_text_then_tool_then_text_assigns_distinct_indices(self):
        """A multi-step run: model emits text + tool call → tool runs → model emits more text.

        Pydantic AI restarts part indices at 0 for each new model response, so
        the converter must assign fresh Agentex message indices.
        """
        events = [
            # First model response: text at index 0, tool call at index 1
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Looking up...")),
            PartEndEvent(index=0, part=TextPart(content="Looking up...")),
            PartStartEvent(
                index=1,
                part=ToolCallPart(tool_name="get_weather", args=None, tool_call_id="c1"),
            ),
            PartDeltaEvent(index=1, delta=ToolCallPartDelta(args_delta="{}")),
            PartEndEvent(index=1, part=ToolCallPart(tool_name="get_weather", args="{}", tool_call_id="c1")),
            FunctionToolResultEvent(
                part=ToolReturnPart(tool_name="get_weather", content="Sunny", tool_call_id="c1"),
            ),
            # Second model response: text restarts at index 0
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="It's sunny.")),
            PartEndEvent(index=0, part=TextPart(content="It's sunny.")),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))

        # Pull every Start/Full event and check their assigned message indices
        anchors = [e for e in out if isinstance(e, (StreamTaskMessageStart, StreamTaskMessageFull))]
        indices = [e.index for e in anchors]
        assert indices == [0, 1, 2, 3], (
            f"Expected 4 distinct, monotonic message indices for: text1, tool_call, tool_result, text2 — got {indices}"
        )

        # And the second text's deltas should target the second text's message index.
        text2_start = anchors[3]
        text2_deltas = [
            e
            for e in out
            if isinstance(e, StreamTaskMessageDelta) and isinstance(e.delta, TextDelta) and e.index == text2_start.index
        ]
        assert len(text2_deltas) == 1
        text2_delta = text2_deltas[0].delta
        assert isinstance(text2_delta, TextDelta)
        assert text2_delta.text_delta == "It's sunny."


class TestIgnoredEvents:
    async def test_function_tool_call_event_is_ignored(self):
        """FunctionToolCallEvent is redundant with PartStart+Delta+End and should be skipped."""
        events = [
            PartStartEvent(
                index=0,
                part=ToolCallPart(tool_name="t", args=None, tool_call_id="c"),
            ),
            FunctionToolCallEvent(
                part=ToolCallPart(tool_name="t", args="{}", tool_call_id="c"),
            ),
            PartEndEvent(index=0, part=ToolCallPart(tool_name="t", args="{}", tool_call_id="c")),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))
        # Start + Done only — no event from FunctionToolCallEvent
        assert len(out) == 2
        assert isinstance(out[0], StreamTaskMessageStart)
        assert isinstance(out[1], StreamTaskMessageDone)

    async def test_final_result_event_ignored(self):
        events = [
            FinalResultEvent(tool_name=None, tool_call_id=None),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))
        assert out == []

    async def test_unknown_part_index_delta_skipped(self):
        events = [
            PartDeltaEvent(index=99, delta=TextPartDelta(content_delta="orphan")),
        ]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))
        assert out == []


class TestStartingTextMatchesAuthor:
    """Sanity check that all emitted content is authored by the agent."""

    @pytest.mark.parametrize(
        "events",
        [
            [PartStartEvent(index=0, part=TextPart(content=""))],
            [PartStartEvent(index=0, part=ThinkingPart(content=""))],
            [
                PartStartEvent(
                    index=0,
                    part=ToolCallPart(tool_name="t", args=None, tool_call_id="c"),
                )
            ],
            [
                FunctionToolResultEvent(
                    part=ToolReturnPart(tool_name="t", content="ok", tool_call_id="c"),
                )
            ],
        ],
    )
    async def test_author_is_agent(self, events: list[Any]):
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))
        for e in out:
            content = getattr(e, "content", None)
            if content is not None and hasattr(content, "author"):
                assert content.author == "agent"


class TestOnResultCallback:
    """on_result callback: captures the terminal AgentRunResultEvent without
    altering streaming output."""

    def _make_result_event(self, output: Any = "hello") -> AgentRunResultEvent:
        result = AgentRunResult(output=output, _output_tool_name=None)
        return AgentRunResultEvent(result=result)

    async def test_callback_invoked_once_with_result_event(self):
        """on_result is called exactly once, with the AgentRunResultEvent."""
        captured: list[AgentRunResultEvent] = []

        def on_result(event: AgentRunResultEvent) -> None:
            captured.append(event)

        result_event = self._make_result_event("the answer")
        events = [result_event]
        await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events), on_result=on_result))

        assert len(captured) == 1
        assert captured[0] is result_event
        assert captured[0].result.output == "the answer"

    async def test_streaming_output_unchanged_with_callback(self):
        """Yielded StreamTaskMessage* sequence is identical whether on_result is set or not."""
        result_event = self._make_result_event()
        events = [
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="hi")),
            PartEndEvent(index=0, part=TextPart(content="hi")),
            result_event,
        ]

        captured: list[AgentRunResultEvent] = []
        out_with = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events), on_result=captured.append))
        out_without = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))

        assert len(out_with) == len(out_without)
        for a, b in zip(out_with, out_without):
            assert type(a) is type(b)
            assert a.model_dump() == b.model_dump()
        assert len(captured) == 1

    async def test_no_callback_no_error(self):
        """AgentRunResultEvent is silently ignored when on_result is None."""
        result_event = self._make_result_event()
        events = [result_event]
        out = await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events)))
        assert out == []

    async def test_async_callback_is_awaited(self):
        """An async on_result callable is properly awaited.

        The callback suspends (``await asyncio.sleep(0)``) before recording its
        side effect, so ``awaited`` is only populated if the converter actually
        awaits the returned coroutine — distinguishing "awaited" from
        "called-but-not-awaited."
        """
        awaited: list[AgentRunResultEvent] = []

        async def on_result_async(event: AgentRunResultEvent) -> None:
            await asyncio.sleep(0)
            awaited.append(event)

        result_event = self._make_result_event("async_output")
        events = [result_event]
        await _collect(convert_pydantic_ai_to_agentex_events(_aiter(events), on_result=on_result_async))

        assert len(awaited) == 1
        assert awaited[0].result.output == "async_output"


# ---------------------------------------------------------------------------
# Unified sync path: PydanticAITurn + UnifiedEmitter.yield_turn
#
# Exercises the path documented in _pydantic_ai_sync.py under
# "Recommended: unified surface":
# - events forwarded by yield_turn equal PydanticAITurn(stream).events (passthrough)
# - with a trace context + fake tracing backend, tool / reasoning spans are derived
# ---------------------------------------------------------------------------


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
