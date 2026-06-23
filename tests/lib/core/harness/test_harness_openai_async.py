"""Integration test: async (Redis-streaming) channel with an OpenAI-agents turn.

Exercises the unified harness surface (UnifiedEmitter.auto_send_turn + OpenAITurn)
with hand-built canonical StreamTaskMessage* streams and a fake streaming
backend so the test runs fully offline (no API keys, no Redis, no Agentex
server).

The canonical event shapes are copied from the OpenAI converter contract
(see tests/lib/core/harness/conformance/test_openai_conformance.py): tool calls
are Full(ToolRequestContent) + Full(ToolResponseContent); text is
Start+Delta+Done.

What is tested
--------------
- auto_send pushes the correct message contexts to the fake streaming backend:
  tool_request + tool_response + text (in that order).
- TurnResult.final_text equals the accumulated text deltas.
- TurnResult carries a TurnUsage; via the OpenAITurn result/converter path the
  aggregated token usage (input/output/total + num_llm_calls) is surfaced in
  TurnResult.usage.
- With a SpanTracer + fake tracing, a tool span is derived on the async path.

What is NOT covered without live infrastructure
-----------------------------------------------
- Actual Redis streaming.
- The ACP on_task_event_send / on_task_create / on_task_cancel lifecycle.
- A real Runner.run_streamed execution / live OpenAI model behaviour.

See also: test_harness_openai_sync.py and test_harness_openai_temporal.py.
"""

from __future__ import annotations

from typing import Any

import pytest
from agents.usage import Usage

from agentex.types.text_delta import TextDelta
from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from tests.lib.core.harness._fakes import FakeTracing
from agentex.lib.core.harness.types import TurnResult, StreamTaskMessage
from agentex.lib.core.harness.tracer import SpanTracer
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

# ---------------------------------------------------------------------------
# Canonical event fixtures (copied from the OpenAI converter contract)
# ---------------------------------------------------------------------------


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
# Fake streaming backend (replaces adk.streaming; no Redis required)
# ---------------------------------------------------------------------------


class _FakeCtx:
    def __init__(self, sink: list[Any], ctype: str, initial_content: Any) -> None:
        self.sink = sink
        self.ctype = ctype
        self.task_message = TaskMessage(id="msg-1", task_id="task1", content=initial_content)

    async def __aenter__(self) -> "_FakeCtx":
        self.sink.append(("open", self.ctype, self.task_message.content))
        return self

    async def __aexit__(self, *args: Any) -> bool:
        await self.close()
        return False

    async def close(self) -> None:
        self.sink.append(("close", self.ctype))

    async def stream_update(self, update: Any) -> Any:
        self.sink.append(("delta", self.ctype, update))
        return update


class _FakeStreaming:
    def __init__(self) -> None:
        self.sink: list[Any] = []
        self.messages_opened: list[Any] = []

    def streaming_task_message_context(
        self,
        task_id: str,
        initial_content: Any,
        streaming_mode: str = "coalesced",
        created_at: Any = None,
    ) -> _FakeCtx:
        ctype = getattr(initial_content, "type", None) or ""
        self.messages_opened.append(initial_content)
        return _FakeCtx(self.sink, ctype, initial_content)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_auto_send_turn(
    events: list[StreamTaskMessage],
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    fake_tracing: FakeTracing | None = None,
) -> tuple[TurnResult, _FakeStreaming]:
    fake_streaming = _FakeStreaming()
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
        streaming=fake_streaming,
    )
    result = await emitter.auto_send_turn(turn)
    return result, fake_streaming


# ---------------------------------------------------------------------------
# Tests: message order and content
# ---------------------------------------------------------------------------


class TestAsyncAutoSendMessageOrder:
    async def test_tool_request_pushed_before_tool_response(self) -> None:
        _, fake_streaming = await _run_auto_send_turn(_tool_then_text_events())
        message_types = [getattr(m, "type", None) for m in fake_streaming.messages_opened]
        assert "tool_request" in message_types
        assert message_types.index("tool_request") < message_types.index("tool_response")

    async def test_text_pushed_last(self) -> None:
        _, fake_streaming = await _run_auto_send_turn(_tool_then_text_events())
        message_types = [getattr(m, "type", None) for m in fake_streaming.messages_opened]
        assert message_types[-1] == "text", f"Expected last message type=text, got {message_types}"

    async def test_exactly_three_messages(self) -> None:
        _, fake_streaming = await _run_auto_send_turn(_tool_then_text_events())
        assert len(fake_streaming.messages_opened) == 3, (
            f"Expected 3 messages, got {[getattr(m, 'type', None) for m in fake_streaming.messages_opened]}"
        )


class TestAsyncAutoSendContentVerification:
    async def test_tool_request_content(self) -> None:
        _, fake_streaming = await _run_auto_send_turn(_tool_then_text_events())
        tool_reqs = [m for m in fake_streaming.messages_opened if isinstance(m, ToolRequestContent)]
        assert len(tool_reqs) == 1
        assert tool_reqs[0].name == "get_weather"

    async def test_tool_response_content(self) -> None:
        _, fake_streaming = await _run_auto_send_turn(_tool_then_text_events())
        tool_resps = [m for m in fake_streaming.messages_opened if isinstance(m, ToolResponseContent)]
        assert len(tool_resps) == 1
        assert "72F" in str(tool_resps[0].content)
        assert tool_resps[0].name == "get_weather"

    async def test_tool_call_ids_match(self) -> None:
        _, fake_streaming = await _run_auto_send_turn(_tool_then_text_events())
        tool_req = next(m for m in fake_streaming.messages_opened if isinstance(m, ToolRequestContent))
        tool_resp = next(m for m in fake_streaming.messages_opened if isinstance(m, ToolResponseContent))
        assert tool_req.tool_call_id == tool_resp.tool_call_id


class TestAsyncAutoSendFinalTextAndUsage:
    async def test_final_text_matches_deltas(self) -> None:
        result, _ = await _run_auto_send_turn(_tool_then_text_events())
        assert result.final_text == "Sunny and 72F."

    async def test_turn_result_has_usage(self) -> None:
        """An injected canonical stream has no run to read usage from, so usage
        carries only the model name (input_tokens stays None)."""
        result, _ = await _run_auto_send_turn(_tool_then_text_events())
        assert result.usage is not None
        assert result.usage.model == "gpt-4o"

    async def test_context_lifecycle_open_then_close(self) -> None:
        _, fake_streaming = await _run_auto_send_turn(_tool_then_text_events())
        opens = [e for e in fake_streaming.sink if e[0] == "open"]
        closes = [e for e in fake_streaming.sink if e[0] == "close"]
        assert len(opens) == len(closes) == 3

    async def test_usage_populated_from_result_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Via the OpenAITurn result/converter path, aggregated token usage is
        surfaced on TurnResult.usage after the stream is consumed.

        Mirrors the OpenAI turn test: a fake RunResultStreaming exposes
        raw_responses with a Usage, and the converter is monkeypatched to a
        passthrough so the canonical text stream is delivered while usage is read
        from raw_responses.
        """
        import agentex.lib.adk._modules._openai_turn as turn_mod

        canonical: list[StreamTaskMessage] = [
            StreamTaskMessageStart(
                type="start", index=0, content=TextContent(type="text", author="agent", content="")
            ),
            StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="hi")),
            StreamTaskMessageDone(type="done", index=0),
        ]

        class _FakeResult:
            def __init__(self) -> None:
                self.raw_responses = [
                    type("R", (), {"usage": Usage(requests=2, input_tokens=8, output_tokens=4, total_tokens=12)})()
                ]

            def stream_events(self):  # type: ignore[no-untyped-def]
                return _canonical_stream(canonical)

        async def _passthrough(stream):  # type: ignore[no-untyped-def]
            async for e in stream:
                yield e

        monkeypatch.setattr(turn_mod, "convert_openai_to_agentex_events", _passthrough)

        turn = OpenAITurn(result=_FakeResult(), model="gpt-4o")
        emitter = UnifiedEmitter(
            task_id="task1",
            trace_id=None,
            parent_span_id=None,
            tracer=False,
            streaming=_FakeStreaming(),
        )
        result = await emitter.auto_send_turn(turn)

        assert result.final_text == "hi"
        assert result.usage.model == "gpt-4o"
        assert result.usage.num_llm_calls == 2
        assert result.usage.input_tokens == 8
        assert result.usage.output_tokens == 4
        assert result.usage.total_tokens == 12


class TestAsyncAutoSendSpanDerivation:
    async def test_tool_span_derived_on_async_path(self) -> None:
        fake_tracing = FakeTracing()
        await _run_auto_send_turn(
            _tool_then_text_events(),
            trace_id="trace1",
            parent_span_id="parent",
            fake_tracing=fake_tracing,
        )
        assert len(fake_tracing.started) == 1
        assert fake_tracing.started[0][0] == "get_weather"
        assert len(fake_tracing.ended) == 1
