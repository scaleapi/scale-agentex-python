"""Integration test: async (Redis-streaming) channel with a pydantic-ai agent.

Exercises the unified harness surface (UnifiedEmitter.auto_send_turn + PydanticAITurn)
with a minimal pydantic-ai agent backed by TestModel so the test runs fully
offline (no API keys, no Redis, no Agentex server).

Agent description
-----------------
Same single-tool agent as the sync test: ``get_weather(city: str) -> str``
returning "sunny and 72F". TestModel is configured to call the tool once then
produce a fixed text reply.

For the async path, ``coalesce_tool_requests=True`` is used (current workaround
for AGX1-377): tool-request Start+Delta+Done sequences are collapsed into a
single Full(ToolRequestContent) before being passed to auto_send, which in turn
opens a streaming context with the full tool_request content and closes it
immediately. This matches the shape the Agentex streaming backend expects for
atomic messages.

What is tested
--------------
- The async handler pushes the correct sequence of messages to the fake streaming
  backend: tool_request + tool_response + text (in that order).
- final_text equals the TestModel custom output.
- With a SpanTracer, tool spans are derived and forwarded to the fake tracing
  backend (note: spans are NOT derived when coalesce_tool_requests=True because
  the tool-request Full event does not trigger an OpenSpan; use the sync path
  for span-derivation coverage with tool calls).

What is NOT covered without live infrastructure
-----------------------------------------------
- Actual Redis streaming (requires a running Redis instance).
- The ACP on_task_event_send / on_task_create / on_task_cancel lifecycle.
- Multi-turn history persistence via adk.state.
- Real LLM calls or production model behaviour.
- The full FastACP async request lifecycle.

See also: test_harness_pydantic_ai_sync.py (span derivation with sync path) and
test_harness_pydantic_ai_temporal.py (temporal activity path).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agentex.types.task_message import TaskMessage
from agentex.lib.core.harness.types import TurnResult
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._pydantic_ai_turn import PydanticAITurn

# ---------------------------------------------------------------------------
# Minimal agent under test
# ---------------------------------------------------------------------------


def _make_agent() -> Agent:
    """Build a pydantic-ai agent with one weather tool and a TestModel."""
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
# Fake streaming backend (replaces adk.streaming; no Redis required)
# ---------------------------------------------------------------------------


class _FakeCtx:
    """Minimal StreamingTaskMessageContext fake."""

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
    """Fake streaming backend; records every context lifecycle event."""

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
# Fake tracing backend
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


async def _run_auto_send_turn(
    agent: Agent,
    user_msg: str = "What is the weather in Paris?",
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    fake_tracing: _FakeTracing | None = None,
) -> tuple[TurnResult, _FakeStreaming]:
    """Drive the async (auto_send) path and return the TurnResult + fake streaming state."""
    fake_streaming = _FakeStreaming()

    tracer: SpanTracer | bool | None = None
    if trace_id and fake_tracing is not None:
        tracer = SpanTracer(
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            task_id="task1",
            tracing=fake_tracing,
        )

    async with agent.run_stream_events(user_msg) as stream:
        turn = PydanticAITurn(
            stream,
            model="test",
            coalesce_tool_requests=True,
        )
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
    """auto_send pushes messages to the streaming backend in canonical order."""

    async def test_tool_request_pushed_first(self) -> None:
        """tool_request is the first message type pushed to the streaming backend."""
        agent = _make_agent()
        _, fake_streaming = await _run_auto_send_turn(agent)

        message_types = [getattr(m, "type", None) for m in fake_streaming.messages_opened]
        assert "tool_request" in message_types
        assert message_types.index("tool_request") < message_types.index("tool_response"), (
            "tool_request must be pushed before tool_response"
        )

    async def test_tool_response_pushed_after_tool_request(self) -> None:
        """tool_response appears after tool_request in the pushed messages."""
        agent = _make_agent()
        _, fake_streaming = await _run_auto_send_turn(agent)

        message_types = [getattr(m, "type", None) for m in fake_streaming.messages_opened]
        assert "tool_response" in message_types

    async def test_text_pushed_last(self) -> None:
        """Text content is the last type pushed (after tool round-trip)."""
        agent = _make_agent()
        _, fake_streaming = await _run_auto_send_turn(agent)

        message_types = [getattr(m, "type", None) for m in fake_streaming.messages_opened]
        assert message_types[-1] == "text", f"Expected last message type=text, got {message_types}"

    async def test_exactly_three_messages(self) -> None:
        """Exactly three message contexts are opened: tool_request, tool_response, text."""
        agent = _make_agent()
        _, fake_streaming = await _run_auto_send_turn(agent)

        assert len(fake_streaming.messages_opened) == 3, (
            f"Expected 3 messages (tool_request + tool_response + text), "
            f"got {len(fake_streaming.messages_opened)}: "
            f"{[getattr(m, 'type', None) for m in fake_streaming.messages_opened]}"
        )


class TestAsyncAutoSendContentVerification:
    """The content pushed to the streaming backend is correct."""

    async def test_tool_request_content(self) -> None:
        """The pushed tool_request is a ToolRequestContent for get_weather."""
        agent = _make_agent()
        _, fake_streaming = await _run_auto_send_turn(agent)

        tool_reqs = [m for m in fake_streaming.messages_opened if isinstance(m, ToolRequestContent)]
        assert len(tool_reqs) == 1, "Expected exactly one ToolRequestContent"
        assert tool_reqs[0].name == "get_weather"

    async def test_tool_response_content(self) -> None:
        """The pushed tool_response is a ToolResponseContent containing the weather result."""
        agent = _make_agent()
        _, fake_streaming = await _run_auto_send_turn(agent)

        tool_resps = [m for m in fake_streaming.messages_opened if isinstance(m, ToolResponseContent)]
        assert len(tool_resps) == 1, "Expected exactly one ToolResponseContent"
        assert "72F" in tool_resps[0].content
        assert tool_resps[0].name == "get_weather"

    async def test_tool_call_ids_match(self) -> None:
        """tool_request and tool_response have the same tool_call_id."""
        agent = _make_agent()
        _, fake_streaming = await _run_auto_send_turn(agent)

        tool_req = next(m for m in fake_streaming.messages_opened if isinstance(m, ToolRequestContent))
        tool_resp = next(m for m in fake_streaming.messages_opened if isinstance(m, ToolResponseContent))
        assert tool_req.tool_call_id == tool_resp.tool_call_id, (
            "tool_request and tool_response must share the same tool_call_id"
        )


class TestAsyncAutoSendFinalText:
    """auto_send_turn returns the accumulated text from the last text part."""

    async def test_final_text_matches_model_output(self) -> None:
        """TurnResult.final_text equals the TestModel custom_output_text."""
        agent = _make_agent()
        result, _ = await _run_auto_send_turn(agent)
        assert result.final_text == "The weather in Paris is sunny and 72F."

    async def test_turn_result_has_usage(self) -> None:
        """TurnResult carries a TurnUsage object (may have None tokens from TestModel)."""
        agent = _make_agent()
        result, _ = await _run_auto_send_turn(agent)
        assert result.usage is not None

    async def test_context_lifecycle_open_then_close(self) -> None:
        """Every message context is opened then closed (no leak)."""
        agent = _make_agent()
        _, fake_streaming = await _run_auto_send_turn(agent)

        opens = [e for e in fake_streaming.sink if e[0] == "open"]
        closes = [e for e in fake_streaming.sink if e[0] == "close"]
        assert len(opens) == len(closes) == 3, "Each of the 3 messages must have exactly one open and one close"


class TestAsyncAutoSendSpanNote:
    """Note: span derivation behaves differently on the async path.

    coalesce_tool_requests=True replaces the tool-request Start+Done sequence with
    a single Full(ToolRequestContent). The SpanDeriver opens a tool span only on
    Done(tool_request), so with coalescing ON the tool span is never opened and
    no spans are derived. Use the sync path (coalesce=False) for span-derivation
    coverage.

    These tests document this expected behaviour and ensure no accidental spans.
    """

    async def test_no_tool_spans_when_coalescing(self) -> None:
        """When coalesce_tool_requests=True, no tool spans are derived."""
        agent = _make_agent()
        fake_tracing = _FakeTracing()
        tracer = SpanTracer(
            trace_id="trace1",
            parent_span_id="parent",
            task_id="task1",
            tracing=fake_tracing,
        )
        fake_streaming = _FakeStreaming()

        async with agent.run_stream_events("What is the weather in Paris?") as stream:
            turn = PydanticAITurn(stream, model="test", coalesce_tool_requests=True)
            emitter = UnifiedEmitter(
                task_id="task1",
                trace_id="trace1",
                parent_span_id="parent",
                tracer=tracer,
                streaming=fake_streaming,
            )
            await emitter.auto_send_turn(turn)

        assert fake_tracing.started == [], (
            "No tool span should be opened when coalescing tool_requests. "
            "Span derivation for the async path requires AGX1-377 to land."
        )
        assert fake_tracing.ended == []


@pytest.mark.parametrize(
    "user_msg",
    [
        "What is the weather in Paris?",
        "Tell me the weather in London.",
    ],
)
async def test_async_handler_pushes_messages_for_various_inputs(user_msg: str) -> None:
    """auto_send pushes at least tool_request + tool_response + text for any input."""
    agent = _make_agent()
    result, fake_streaming = await _run_auto_send_turn(agent, user_msg=user_msg)

    message_types = [getattr(m, "type", None) for m in fake_streaming.messages_opened]
    assert "tool_request" in message_types
    assert "tool_response" in message_types
    assert "text" in message_types
    assert isinstance(result.final_text, str)
    assert len(result.final_text) > 0
