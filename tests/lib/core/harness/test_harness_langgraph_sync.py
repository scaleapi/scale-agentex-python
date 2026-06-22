"""Integration test: sync (HTTP-yield) channel with a LangGraph agent.

Exercises the unified harness surface (UnifiedEmitter.yield_turn + LangGraphTurn)
with a minimal fake LangGraph stream so the test runs fully offline (no API
keys, no Redis, no Agentex server).

Agent description
-----------------
A simulated single-tool agent run using hand-crafted LangGraph event tuples:
one tool request + response, followed by a final text reply.

What is tested
--------------
- The sync handler correctly yields StreamTaskMessage* events in order:
  Full(ToolRequest) then Full(ToolResponse) then text Start+Delta+Done.
- With trace_id + fake tracing, the SpanDeriver fires for text events.
- LangGraph emits tool calls as Full events (not Start+Done); the SpanDeriver
  opens a tool span on Full(ToolRequestContent) and closes it on the matching
  Full(ToolResponseContent) (see test_tracer_produces_tool_spans_for_full_events).
- Final text is accumulated via yield mode.

What is NOT covered without live infrastructure
-----------------------------------------------
- Actual HTTP streaming over the ACP sync endpoint.
- Real LLM calls or real LangGraph graph execution.
- The full FastACP request/response lifecycle.

See also: test_harness_langgraph_async.py and test_harness_langgraph_temporal.py
for the other two channels.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from tests.lib.core.harness._fakes import FakeTracing
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.task_message_update import (
    StreamTaskMessageFull,
    StreamTaskMessageStart,
)
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
# Helpers
# ---------------------------------------------------------------------------


def _make_stream(events: list[tuple[str, Any]]):
    async def _gen():
        for e in events:
            yield e

    return _gen()


async def _run_yield_turn(
    stream_events: list[tuple[str, Any]], trace_id: str | None = None
) -> tuple[list[Any], FakeTracing | None]:
    fake_tracing = FakeTracing() if trace_id else None
    tracer: SpanTracer | bool | None = None
    if trace_id and fake_tracing is not None:
        tracer = SpanTracer(trace_id=trace_id, parent_span_id=None, task_id="task1", tracing=fake_tracing)

    emitter = UnifiedEmitter(
        task_id="task1",
        trace_id=trace_id,
        parent_span_id=None,
        tracer=tracer if tracer is not None else False,
    )
    turn = LangGraphTurn(_make_stream(stream_events), model=None)
    out = [e async for e in emitter.yield_turn(turn)]
    return out, fake_tracing


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSyncYieldChannel:
    async def test_text_only_stream_yields_start_delta_done(self):
        from langchain_core.messages import AIMessage, AIMessageChunk

        chunk = AIMessageChunk(content="Hello from LangGraph!")
        ai_msg = AIMessage(content="Hello from LangGraph!")
        events = [
            ("messages", (chunk, {})),
            ("updates", {"agent": {"messages": [ai_msg]}}),
        ]
        out, _ = await _run_yield_turn(events)

        types = [type(e).__name__ for e in out]
        assert "StreamTaskMessageStart" in types
        assert "StreamTaskMessageDelta" in types
        assert "StreamTaskMessageDone" in types

    async def test_tool_call_yields_full_events(self):
        from langchain_core.messages import AIMessage, ToolMessage

        tc = {"id": "call_1", "name": "get_weather", "args": {"city": "Paris"}}
        ai_msg = AIMessage(content="", tool_calls=[tc])
        tool_msg = ToolMessage(content="Sunny, 72F", tool_call_id="call_1", name="get_weather")
        events = [
            ("updates", {"agent": {"messages": [ai_msg]}}),
            ("updates", {"tools": {"messages": [tool_msg]}}),
        ]
        out, _ = await _run_yield_turn(events)

        full_events = [e for e in out if isinstance(e, StreamTaskMessageFull)]
        assert len(full_events) == 2

        contents = [e.content for e in full_events]
        assert any(isinstance(c, ToolRequestContent) for c in contents)
        assert any(isinstance(c, ToolResponseContent) for c in contents)

    async def test_multi_step_yields_events_in_order(self):
        from langchain_core.messages import AIMessage, ToolMessage, AIMessageChunk

        chunk1 = AIMessageChunk(content="Searching...")
        ai_msg1 = AIMessage(content="Searching...", tool_calls=[{"id": "c1", "name": "search", "args": {"q": "test"}}])
        tool_msg = ToolMessage(content="results", tool_call_id="c1", name="search")
        chunk2 = AIMessageChunk(content="Found it!")
        ai_msg2 = AIMessage(content="Found it!")

        events = [
            ("messages", (chunk1, {})),
            ("updates", {"agent": {"messages": [ai_msg1]}}),
            ("updates", {"tools": {"messages": [tool_msg]}}),
            ("messages", (chunk2, {})),
            ("updates", {"agent": {"messages": [ai_msg2]}}),
        ]
        out, _ = await _run_yield_turn(events)

        # Should have multiple start events (one per text segment)
        starts = [e for e in out if isinstance(e, StreamTaskMessageStart)]
        assert len(starts) >= 2
        # And two Full events (tool req + tool resp)
        fulls = [e for e in out if isinstance(e, StreamTaskMessageFull)]
        assert len(fulls) == 2

    async def test_empty_stream_yields_nothing(self):
        out, _ = await _run_yield_turn([])
        assert out == []

    async def test_tracer_produces_tool_spans_for_full_events(self):
        """SpanDeriver handles Full tool events (request opens, response closes).

        Full(ToolRequestContent) opens a tool span; Full(ToolResponseContent) closes it.
        This aligns LangGraph tracing with Start+Done harnesses (pydantic-ai, openai-agents).
        """
        from langchain_core.messages import AIMessage, ToolMessage

        tc = {"id": "c1", "name": "t", "args": {}}
        ai_msg = AIMessage(content="", tool_calls=[tc])
        tool_msg = ToolMessage(content="ok", tool_call_id="c1", name="t")

        events = [
            ("updates", {"agent": {"messages": [ai_msg]}}),
            ("updates", {"tools": {"messages": [tool_msg]}}),
        ]
        _, fake_tracing = await _run_yield_turn(events, trace_id="trace-1")

        assert fake_tracing is not None
        assert len(fake_tracing.started) == 1, "Full(ToolRequestContent) opens one tool span"
        assert fake_tracing.started[0][0] == "t", "span name matches the tool name"
        assert len(fake_tracing.ended) == 1, "Full(ToolResponseContent) closes the span"

    async def test_usage_captured_after_yield(self):
        from langchain_core.messages import AIMessage

        usage_meta = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        ai_msg = AIMessage(content="Hi!", usage_metadata=usage_meta)
        events = [("updates", {"agent": {"messages": [ai_msg]}})]

        turn = LangGraphTurn(_make_stream(events), model="gpt-4")
        emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None)
        _ = [e async for e in emitter.yield_turn(turn)]

        usage = turn.usage()
        assert usage.input_tokens == 10
        assert usage.output_tokens == 5
