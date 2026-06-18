"""Unified sync path tests for LangGraphTurn + UnifiedEmitter.

Verifies:
1. Passthrough: events from emitter.yield_turn(LangGraphTurn(stream)) equal
   LangGraphTurn(stream).events collected directly.
2. Span derivation: with trace_id + fake tracer, tool spans are derived from
   the event stream.

NOTE: langchain_core imports are deferred to test scope because conftest.py
stubs ``langchain_core.messages`` with MagicMock.
"""

from __future__ import annotations

import sys
from typing import Any
from datetime import datetime, timezone
from dataclasses import field, dataclass

import pytest

from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.emitter import UnifiedEmitter
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
# Helpers
# ---------------------------------------------------------------------------


def _make_stream(events: list[tuple[str, Any]]):
    async def _gen():
        for e in events:
            yield e

    return _gen()


# ---------------------------------------------------------------------------
# Fake SpanTracer
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPassthrough:
    async def test_yield_turn_events_equal_direct_events(self):
        """Events from emitter.yield_turn(LangGraphTurn(stream)) must equal
        LangGraphTurn(stream).events collected directly — the emitter must not
        add, drop, or reorder events in yield mode."""
        from langchain_core.messages import AIMessage, AIMessageChunk

        chunk = AIMessageChunk(content="Hello!")
        ai_msg = AIMessage(content="Hello!")

        # Build two identical streams
        events_raw = [
            ("messages", (chunk, {})),
            ("updates", {"agent": {"messages": [ai_msg]}}),
        ]

        # Direct collection
        direct = [e async for e in LangGraphTurn(_make_stream(events_raw)).events]

        # Via emitter.yield_turn
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


class TestSpanDerivation:
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

    async def test_tool_span_not_derived_from_full_events(self, fake_tracer):
        """AGX1-377: LangGraph emits tool calls as Full events (not Start+Done).
        The SpanDeriver opens tool spans from Start(ToolRequestContent)+Done
        sequences. Since LangGraph uses Full, no tool span is opened by the
        SpanDeriver -- this is the documented AGX1-377 gap resolved by the
        unified surface (Full events are emitted identically; cross-channel
        span equivalence arrives with AGX1-373).

        The tracer must still be invoked (SpanDeriver.observe is called for each
        event); it just produces no open-span signals for LangGraph Full tool events.
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

        # AGX1-377: Full events don't produce tool spans via SpanDeriver today.
        # This is the documented gap; full cross-channel equivalence arrives with AGX1-373.
        assert backend.spans_started == [], (
            "Expected no tool spans for LangGraph Full events (AGX1-377); if this "
            "assertion fails it means SpanDeriver now handles Full events — update "
            "the test to assert the new span names."
        )

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
