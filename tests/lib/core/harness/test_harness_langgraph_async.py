"""Integration test: async (Redis-streaming) channel with a LangGraph agent.

Exercises the unified harness surface (UnifiedEmitter.auto_send_turn + LangGraphTurn)
with a minimal fake LangGraph stream so the test runs fully offline (no API
keys, no Redis, no Agentex server).

Agent description
-----------------
A simulated single-tool agent run using hand-crafted LangGraph event tuples:
one tool request + response, followed by a final text reply.

What is tested
--------------
- The async handler pushes the correct sequence of messages to the fake streaming
  backend: Full(ToolRequest) + Full(ToolResponse) + text Start/Delta/Done.
- final_text accumulates all text (not just last segment — AGX1-377 unified behavior).
- Tool messages go through streaming_task_message_context (not messages.create).
- With a SpanTracer, no tool spans are produced (AGX1-377: Full events are not
  handled by SpanDeriver today).

What is NOT covered without live infrastructure
-----------------------------------------------
- Actual Redis streaming (requires a running Redis instance).
- The ACP on_task_event_send / on_task_create / on_task_cancel lifecycle.
- Real LLM calls or real LangGraph graph execution.
- The full FastACP async request lifecycle.

See also: test_harness_langgraph_sync.py and test_harness_langgraph_temporal.py
for the other two channels.
"""

from __future__ import annotations

import sys
from typing import Any
from dataclasses import field, dataclass

import pytest

from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.lib.core.harness.types import TurnResult
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._langgraph_turn import LangGraphTurn

# ---------------------------------------------------------------------------
# Remove conftest stubs so real langchain_core types are used
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _real_langchain_core():
    stub_keys = [k for k in sys.modules if k.startswith("langchain_core") or k.startswith("langgraph")]
    saved = {k: sys.modules.pop(k) for k in stub_keys}
    import importlib

    importlib.import_module("langchain_core.messages")
    yield
    sys.modules.update(saved)


# ---------------------------------------------------------------------------
# Fake streaming backend (replaces adk.streaming; no Redis required)
# ---------------------------------------------------------------------------


@dataclass
class _FakeCtx:
    ctype: str
    initial_content: Any
    task_message: TaskMessage
    closed: bool = False
    deltas: list[Any] = field(default_factory=list)

    async def __aenter__(self) -> "_FakeCtx":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        await self.close()
        return False

    async def close(self) -> None:
        self.closed = True

    async def stream_update(self, update: Any) -> Any:
        self.deltas.append(update)
        return update


class _FakeStreaming:
    def __init__(self) -> None:
        self.contexts: list[_FakeCtx] = []

    def streaming_task_message_context(self, task_id: str, initial_content: Any, **kw: Any) -> _FakeCtx:
        ctype = getattr(initial_content, "type", None) or ""
        tm = TaskMessage(id=f"m{len(self.contexts) + 1}", task_id=task_id, content=initial_content)
        ctx = _FakeCtx(ctype=ctype, initial_content=initial_content, task_message=tm)
        self.contexts.append(ctx)
        return ctx


# ---------------------------------------------------------------------------
# Fake tracing backend
# ---------------------------------------------------------------------------


class _FakeSpan:
    def __init__(self, name: str) -> None:
        self.name = name
        self.output: Any = None


class _FakeTracing:
    def __init__(self) -> None:
        self.started: list[tuple[str, Any]] = []
        self.ended: list[tuple[str, Any]] = []

    async def start_span(self, *, trace_id: str, name: str, **kw: Any) -> _FakeSpan:
        self.started.append((name, kw.get("parent_id")))
        return _FakeSpan(name)

    async def end_span(self, *, trace_id: str, span: _FakeSpan) -> None:
        self.ended.append((span.name, span.output))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stream(events: list[tuple[str, Any]]):
    async def _gen():
        for e in events:
            yield e

    return _gen()


async def _run_auto_send_turn(
    stream_events: list[tuple[str, Any]],
    trace_id: str | None = None,
) -> tuple[TurnResult, _FakeStreaming, _FakeTracing | None]:
    fake_streaming = _FakeStreaming()
    fake_tracing = _FakeTracing() if trace_id else None

    tracer: SpanTracer | bool = False
    if trace_id and fake_tracing is not None:
        tracer = SpanTracer(trace_id=trace_id, parent_span_id=None, task_id="task1", tracing=fake_tracing)

    turn = LangGraphTurn(_make_stream(stream_events), model=None)
    emitter = UnifiedEmitter(
        task_id="task1",
        trace_id=trace_id,
        parent_span_id=None,
        tracer=tracer,
        streaming=fake_streaming,
    )
    result = await emitter.auto_send_turn(turn)
    return result, fake_streaming, fake_tracing


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAsyncAutoSendChannel:
    async def test_text_only_streams_text_and_returns_final(self):
        from langchain_core.messages import AIMessage, AIMessageChunk

        chunk = AIMessageChunk(content="Hello from LangGraph!")
        ai_msg = AIMessage(content="Hello from LangGraph!")
        events = [
            ("messages", (chunk, {})),
            ("updates", {"agent": {"messages": [ai_msg]}}),
        ]
        result, fake_streaming, _ = await _run_auto_send_turn(events)

        assert result.final_text == "Hello from LangGraph!"
        text_ctxs = [c for c in fake_streaming.contexts if c.ctype == "text"]
        assert len(text_ctxs) == 1
        assert text_ctxs[0].closed is True

    async def test_tool_call_posted_via_streaming_context(self):
        from langchain_core.messages import AIMessage

        tc = {"id": "call_1", "name": "get_weather", "args": {"city": "Paris"}}
        ai_msg = AIMessage(content="", tool_calls=[tc])
        events = [("updates", {"agent": {"messages": [ai_msg]}})]

        result, fake_streaming, _ = await _run_auto_send_turn(events)

        # Tool request via streaming_task_message_context (Full event)
        tool_req_ctxs = [c for c in fake_streaming.contexts if isinstance(c.initial_content, ToolRequestContent)]
        assert len(tool_req_ctxs) == 1
        assert tool_req_ctxs[0].initial_content.tool_call_id == "call_1"
        assert tool_req_ctxs[0].closed is True
        assert tool_req_ctxs[0].deltas == [], "Full messages have no deltas"

    async def test_tool_response_posted_via_streaming_context(self):
        from langchain_core.messages import ToolMessage

        tool_msg = ToolMessage(content="Sunny, 72F", tool_call_id="call_1", name="get_weather")
        events = [("updates", {"tools": {"messages": [tool_msg]}})]

        _, fake_streaming, _ = await _run_auto_send_turn(events)

        tool_resp_ctxs = [c for c in fake_streaming.contexts if isinstance(c.initial_content, ToolResponseContent)]
        assert len(tool_resp_ctxs) == 1
        assert tool_resp_ctxs[0].initial_content.content == "Sunny, 72F"
        assert tool_resp_ctxs[0].closed is True

    async def test_multi_step_accumulates_all_text(self):
        """Unified surface: final_text accumulates all text, not just last segment."""
        from langchain_core.messages import AIMessage, ToolMessage, AIMessageChunk

        chunk1 = AIMessageChunk(content="Searching...")
        ai_msg1 = AIMessage(content="Searching...", tool_calls=[{"id": "c1", "name": "s", "args": {}}])
        tool_msg = ToolMessage(content="results", tool_call_id="c1", name="s")
        chunk2 = AIMessageChunk(content="Found it!")
        ai_msg2 = AIMessage(content="Found it!")

        events = [
            ("messages", (chunk1, {})),
            ("updates", {"agent": {"messages": [ai_msg1]}}),
            ("updates", {"tools": {"messages": [tool_msg]}}),
            ("messages", (chunk2, {})),
            ("updates", {"agent": {"messages": [ai_msg2]}}),
        ]
        result, fake_streaming, _ = await _run_auto_send_turn(events)

        # All text accumulated
        assert "Searching..." in result.final_text
        assert "Found it!" in result.final_text

        # Two text streaming contexts
        text_ctxs = [c for c in fake_streaming.contexts if isinstance(c.initial_content, TextContent)]
        assert len(text_ctxs) == 2

    async def test_empty_stream_returns_empty_final_text(self):
        result, fake_streaming, _ = await _run_auto_send_turn([])
        assert result.final_text == ""
        assert fake_streaming.contexts == []

    async def test_turn_usage_populated_after_events_consumed(self):
        """LangGraphTurn.usage() is populated via the on_final_ai_message callback
        during event iteration. TurnResult.usage is a snapshot from before events run
        (emitter.auto_send_turn evaluates turn.usage() eagerly); the authoritative
        post-iteration usage is on turn.usage() directly."""
        from langchain_core.messages import AIMessage

        fake_streaming = _FakeStreaming()
        usage_meta = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        ai_msg = AIMessage(content="hi", usage_metadata=usage_meta)
        events = [("updates", {"agent": {"messages": [ai_msg]}})]

        turn = LangGraphTurn(_make_stream(events), model="gpt-4")
        emitter = UnifiedEmitter(
            task_id="task1", trace_id=None, parent_span_id=None, tracer=False, streaming=fake_streaming
        )
        await emitter.auto_send_turn(turn)

        # After auto_send_turn, turn.usage() has the captured values
        usage = turn.usage()
        assert usage.input_tokens == 10
        assert usage.output_tokens == 5
        assert usage.total_tokens == 15

    async def test_tracer_does_not_produce_tool_spans_for_full_events(self):
        """AGX1-377: Full events don't trigger SpanDeriver tool spans."""
        from langchain_core.messages import AIMessage, ToolMessage

        tc = {"id": "c1", "name": "t", "args": {}}
        ai_msg = AIMessage(content="", tool_calls=[tc])
        tool_msg = ToolMessage(content="ok", tool_call_id="c1", name="t")

        events = [
            ("updates", {"agent": {"messages": [ai_msg]}}),
            ("updates", {"tools": {"messages": [tool_msg]}}),
        ]
        _, _, fake_tracing = await _run_auto_send_turn(events, trace_id="trace-1")

        assert fake_tracing is not None
        assert fake_tracing.started == [], "AGX1-377: Full events don't trigger tool spans"
