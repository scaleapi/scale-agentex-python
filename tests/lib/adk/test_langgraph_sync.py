"""Tests for the sync LangGraph -> Agentex path.

Covers:
- The bare converter ``convert_langgraph_to_agentex_events``:
    * Basic text, tool call, and tool response emission
    * on_final_ai_message callback for usage capture
- The unified sync (HTTP ACP) path ``UnifiedEmitter.yield_turn(LangGraphTurn(...))``:
    * Passthrough: yield_turn events equal LangGraphTurn(stream).events
    * Span derivation from Full tool events with a fake tracer

NOTE: langchain_core imports must be deferred to test-function scope because
conftest.py stubs out ``langchain_core.messages`` with MagicMock for ADK
package-level tests. The real classes are imported lazily inside each test.
"""

from __future__ import annotations

import sys
from typing import Any, AsyncIterator
from datetime import datetime, timezone
from dataclasses import field, dataclass

import pytest

from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.task_message_update import (
    StreamTaskMessageFull,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._langgraph_sync import convert_langgraph_to_agentex_events
from agentex.lib.adk._modules._langgraph_turn import LangGraphTurn

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect(stream: AsyncIterator[Any]) -> list[Any]:
    return [e async for e in stream]


def _make_stream(events: list[tuple[str, Any]]) -> AsyncIterator[tuple[str, Any]]:
    async def _gen():
        for e in events:
            yield e

    return _gen()


# ---------------------------------------------------------------------------
# Remove the conftest stubs for langchain_core so real classes are used
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _real_langchain_core():
    """Remove conftest MagicMock stubs so real langchain_core types are used."""
    stub_keys = [k for k in sys.modules if k.startswith("langchain_core") or k.startswith("langgraph")]
    saved = {k: sys.modules.pop(k) for k in stub_keys}
    # Re-import the real modules
    import importlib

    importlib.import_module("langchain_core.messages")
    yield
    # Restore stubs after the test
    sys.modules.update(saved)


class TestTextStreaming:
    async def test_plain_text_emits_start_delta_done(self):
        from langchain_core.messages import AIMessage, AIMessageChunk

        chunk = AIMessageChunk(content="Hello, world!")
        events = [
            ("messages", (chunk, {})),
            ("updates", {"agent": {"messages": [AIMessage(content="Hello, world!")]}}),
        ]
        out = await _collect(convert_langgraph_to_agentex_events(_make_stream(events)))
        types = [type(e).__name__ for e in out]
        assert "StreamTaskMessageStart" in types
        assert "StreamTaskMessageDelta" in types
        assert "StreamTaskMessageDone" in types

    async def test_empty_chunk_content_is_skipped(self):
        from langchain_core.messages import AIMessageChunk

        chunk = AIMessageChunk(content="")
        events = [("messages", (chunk, {}))]
        out = await _collect(convert_langgraph_to_agentex_events(_make_stream(events)))
        assert out == []

    async def test_reasoning_block_start_wraps_reasoning_content(self):
        """A Responses-API reasoning block opens a Start wrapping ReasoningContent,
        not TextContent (the deltas are ReasoningContentDelta)."""
        from langchain_core.messages import AIMessageChunk

        from agentex.types.reasoning_content import ReasoningContent
        from agentex.types.task_message_update import StreamTaskMessageDelta, StreamTaskMessageStart
        from agentex.types.reasoning_content_delta import ReasoningContentDelta

        chunk = AIMessageChunk(
            content=[{"type": "reasoning", "summary": [{"type": "summary_text", "text": "thinking hard"}]}]
        )
        events = [("messages", (chunk, {}))]
        out = await _collect(convert_langgraph_to_agentex_events(_make_stream(events)))
        starts = [e for e in out if isinstance(e, StreamTaskMessageStart)]
        assert len(starts) == 1
        assert isinstance(starts[0].content, ReasoningContent), "reasoning Start must wrap ReasoningContent"
        # `style` must be a non-null MessageStyle: the AgentEx server's
        # StreamTaskMessageStartEntity rejects `reasoning.style=None` (enum), which
        # would kill the stream. Match the conformance fixture's canonical value.
        assert starts[0].content.style == "active", "reasoning Start must set a non-null style ('active')"
        # Pull content_delta inside the comprehension so the isinstance narrows the
        # delta union (narrowing would not survive a later attribute access).
        reasoning_delta_texts = [
            e.delta.content_delta
            for e in out
            if isinstance(e, StreamTaskMessageDelta) and isinstance(e.delta, ReasoningContentDelta)
        ]
        assert reasoning_delta_texts == ["thinking hard"]


class TestToolCallEmission:
    async def test_tool_call_emits_full_message(self):
        from langchain_core.messages import AIMessage

        tc = {"id": "call_1", "name": "get_weather", "args": {"city": "Paris"}}
        ai_msg = AIMessage(content="", tool_calls=[tc])
        events = [("updates", {"agent": {"messages": [ai_msg]}})]
        out = await _collect(convert_langgraph_to_agentex_events(_make_stream(events)))
        assert len(out) == 1
        assert isinstance(out[0], StreamTaskMessageFull)
        content = out[0].content
        assert isinstance(content, ToolRequestContent)
        assert content.tool_call_id == "call_1"
        assert content.name == "get_weather"
        assert content.arguments == {"city": "Paris"}
        assert content.author == "agent"

    async def test_tool_response_emits_full_message(self):
        from langchain_core.messages import ToolMessage

        tool_msg = ToolMessage(content="Sunny, 72F", tool_call_id="call_1", name="get_weather")
        events = [("updates", {"tools": {"messages": [tool_msg]}})]
        out = await _collect(convert_langgraph_to_agentex_events(_make_stream(events)))
        assert len(out) == 1
        assert isinstance(out[0], StreamTaskMessageFull)
        content = out[0].content
        assert isinstance(content, ToolResponseContent)
        assert content.tool_call_id == "call_1"
        assert content.name == "get_weather"
        assert content.content == "Sunny, 72F"
        assert content.author == "agent"


class TestOnFinalAiMessageCallback:
    async def test_callback_called_for_ai_message_in_agent_node(self):
        from langchain_core.messages import AIMessage

        captured: list[Any] = []
        ai_msg = AIMessage(content="Hello!")

        events = [("updates", {"agent": {"messages": [ai_msg]}})]
        await _collect(convert_langgraph_to_agentex_events(_make_stream(events), on_final_ai_message=captured.append))
        assert len(captured) == 1
        assert captured[0] is ai_msg

    async def test_callback_not_called_for_tool_messages(self):
        from langchain_core.messages import ToolMessage

        captured: list[Any] = []
        tool_msg = ToolMessage(content="result", tool_call_id="c1", name="t")

        events = [("updates", {"tools": {"messages": [tool_msg]}})]
        await _collect(convert_langgraph_to_agentex_events(_make_stream(events), on_final_ai_message=captured.append))
        assert captured == []

    async def test_callback_receives_usage_metadata(self):
        from langchain_core.messages import AIMessage

        captured: list[Any] = []
        usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        ai_msg = AIMessage(content="Answer.", usage_metadata=usage)

        events = [("updates", {"agent": {"messages": [ai_msg]}})]
        await _collect(convert_langgraph_to_agentex_events(_make_stream(events), on_final_ai_message=captured.append))
        assert len(captured) == 1
        assert captured[0].usage_metadata == usage

    async def test_no_callback_is_noop(self):
        from langchain_core.messages import AIMessage

        ai_msg = AIMessage(content="Hello!")
        events = [("updates", {"agent": {"messages": [ai_msg]}})]
        out = await _collect(convert_langgraph_to_agentex_events(_make_stream(events)))
        assert isinstance(out, list)

    async def test_callback_called_multiple_times_for_multi_step(self):
        from langchain_core.messages import AIMessage

        captured: list[Any] = []
        ai_msg_1 = AIMessage(content="Step 1")
        ai_msg_2 = AIMessage(content="Step 2")

        events = [
            ("updates", {"agent": {"messages": [ai_msg_1]}}),
            ("updates", {"agent": {"messages": [ai_msg_2]}}),
        ]
        await _collect(convert_langgraph_to_agentex_events(_make_stream(events), on_final_ai_message=captured.append))
        assert len(captured) == 2
        assert captured[0] is ai_msg_1
        assert captured[1] is ai_msg_2

    async def test_callback_called_after_tool_call_events_yielded(self):
        """The callback fires after all events for that AIMessage are yielded."""
        from langchain_core.messages import AIMessage

        yield_order: list[str] = []

        async def _gen():
            tc = {"id": "c1", "name": "t", "args": {}}
            ai_msg = AIMessage(content="", tool_calls=[tc])
            yield ("updates", {"agent": {"messages": [ai_msg]}})

        def _cb(msg):
            yield_order.append("callback")

        async for _ in convert_langgraph_to_agentex_events(_gen(), on_final_ai_message=_cb):
            yield_order.append("event")

        # The tool call Full event is emitted before the callback fires
        assert yield_order.index("event") < yield_order.index("callback")


# ---------------------------------------------------------------------------
# Unified sync path: LangGraphTurn + UnifiedEmitter.yield_turn
#
# Verifies the sync (HTTP ACP) delivery surface:
# 1. Passthrough: events from emitter.yield_turn(LangGraphTurn(stream)) equal
#    LangGraphTurn(stream).events collected directly.
# 2. Span derivation: with trace_id + fake tracer, tool spans are derived from
#    the event stream.
# ---------------------------------------------------------------------------


@dataclass
class _FakeTracingBackend:
    spans_started: list[dict[str, Any]] = field(default_factory=list)
    spans_ended: list[str] = field(default_factory=list)

    async def start_span(self, **kw) -> Any:
        from agentex.types.span import Span

        sp = Span(
            id=f"span-{len(self.spans_started) + 1}",
            trace_id=kw.get("trace_id", "trace1"),
            name=kw.get("name", ""),
            start_time=datetime.now(tz=timezone.utc),
        )
        self.spans_started.append(kw)
        return sp

    async def end_span(self, *, trace_id: str, span: Any) -> None:
        self.spans_ended.append(span.id if span else "")


class TestUnifiedSyncPathPassthrough:
    async def test_yield_turn_events_equal_direct_events(self):
        """Events from emitter.yield_turn(LangGraphTurn(stream)) must equal
        LangGraphTurn(stream).events collected directly — the emitter must not
        add, drop, or reorder events in yield mode."""
        from langchain_core.messages import AIMessage, AIMessageChunk

        chunk = AIMessageChunk(content="Hello!")
        ai_msg = AIMessage(content="Hello!")

        events_raw = [
            ("messages", (chunk, {})),
            ("updates", {"agent": {"messages": [ai_msg]}}),
        ]

        direct = [e async for e in LangGraphTurn(_make_stream(events_raw)).events]

        emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None)
        via_emitter = [e async for e in emitter.yield_turn(LangGraphTurn(_make_stream(events_raw)))]

        assert len(direct) == len(via_emitter), "yield_turn must not add or drop events relative to direct iteration"
        for a, b in zip(direct, via_emitter, strict=True):
            assert type(a) == type(b), f"Event type mismatch: {type(a).__name__} vs {type(b).__name__}"

    async def test_yield_turn_passes_all_event_types(self):
        """Start, Delta, Done, Full — each type is preserved."""
        from langchain_core.messages import AIMessage, AIMessageChunk

        chunk = AIMessageChunk(content="hi")
        tc = {"id": "c1", "name": "t", "args": {}}
        ai_msg = AIMessage(content="hi", tool_calls=[tc])

        events_raw = [
            ("messages", (chunk, {})),
            ("updates", {"agent": {"messages": [ai_msg]}}),
        ]
        emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None)
        out = [e async for e in emitter.yield_turn(LangGraphTurn(_make_stream(events_raw)))]
        types = {type(e).__name__ for e in out}
        # text chunk emits Start + Delta
        assert "StreamTaskMessageStart" in types
        assert "StreamTaskMessageDelta" in types
        # tool call emits Full
        assert "StreamTaskMessageFull" in types

    async def test_empty_stream_yields_no_events(self):
        emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None)
        out = [e async for e in emitter.yield_turn(LangGraphTurn(_make_stream([])))]
        assert out == []


class TestUnifiedSyncPathSpanDerivation:
    @pytest.fixture
    def fake_tracer(self):
        backend = _FakeTracingBackend()
        tracer = SpanTracer(
            trace_id="trace1",
            parent_span_id=None,
            task_id="t",
            tracing=backend,  # type: ignore[arg-type]
        )
        return tracer, backend

    async def test_tool_span_derived_from_full_events(self, fake_tracer):
        """SpanDeriver handles Full tool events for LangGraph.

        Full(ToolRequestContent) opens a tool span keyed by tool_call_id;
        Full(ToolResponseContent) closes it, aligning LangGraph's Full-event
        path with the Start+Done harnesses (pydantic-ai, openai-agents).
        """
        from langchain_core.messages import AIMessage, ToolMessage

        tracer, backend = fake_tracer
        tc = {"id": "c1", "name": "get_weather", "args": {"city": "Paris"}}
        ai_msg = AIMessage(content="", tool_calls=[tc])
        tool_msg = ToolMessage(content="Sunny", tool_call_id="c1", name="get_weather")

        events_raw = [
            ("updates", {"agent": {"messages": [ai_msg]}}),
            ("updates", {"tools": {"messages": [tool_msg]}}),
        ]

        emitter = UnifiedEmitter(task_id="t", trace_id="trace1", parent_span_id=None, tracer=tracer)
        _ = [e async for e in emitter.yield_turn(LangGraphTurn(_make_stream(events_raw)))]

        assert len(backend.spans_started) == 1, "Full(ToolRequestContent) opens one tool span"
        started = backend.spans_started[0]
        assert started["name"] == "get_weather"
        assert started["input"] == {"city": "Paris"}

    async def test_no_spans_when_no_tool_calls(self, fake_tracer):
        """yield_turn with tracer but no tool calls emits no spans."""
        from langchain_core.messages import AIMessage, AIMessageChunk

        tracer, backend = fake_tracer
        chunk = AIMessageChunk(content="Hello!")
        ai_msg = AIMessage(content="Hello!")

        events_raw = [
            ("messages", (chunk, {})),
            ("updates", {"agent": {"messages": [ai_msg]}}),
        ]

        emitter = UnifiedEmitter(task_id="t", trace_id="trace1", parent_span_id=None, tracer=tracer)
        _ = [e async for e in emitter.yield_turn(LangGraphTurn(_make_stream(events_raw)))]

        assert backend.spans_started == [], "No tool spans when there are no tool calls"

    async def test_tracer_none_means_no_spans(self):
        """With tracer=False, no spans should be emitted."""
        from langchain_core.messages import AIMessage, ToolMessage

        tc = {"id": "c1", "name": "t", "args": {}}
        ai_msg = AIMessage(content="", tool_calls=[tc])
        tool_msg = ToolMessage(content="ok", tool_call_id="c1", name="t")

        events_raw = [
            ("updates", {"agent": {"messages": [ai_msg]}}),
            ("updates", {"tools": {"messages": [tool_msg]}}),
        ]

        emitter = UnifiedEmitter(task_id="t", trace_id="trace1", parent_span_id=None, tracer=False)
        _ = [e async for e in emitter.yield_turn(LangGraphTurn(_make_stream(events_raw)))]
        # No assertion on spans since tracer=False means emitter.tracer is None
        assert emitter.tracer is None
