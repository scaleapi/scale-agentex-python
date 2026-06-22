"""Tests for auto_send delivery adapter.

The fake mirrors the real StreamingTaskMessageContext API exactly:
- streaming_task_message_context(...) returns a context object (synchronously)
- open the context via __aenter__ (returns self after creating the task message)
- stream deltas via ctx.stream_update(StreamTaskMessageDelta(...))
- close via ctx.close() (NOT __aexit__)

This mirrors _langgraph_async.py lines 62-78 and 100-127.
"""

import types as _types
from datetime import datetime

import pytest

from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.types.task_message_delta import TextDelta
from agentex.types.tool_request_delta import ToolRequestDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.lib.core.harness.auto_send import auto_send
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent


class _FakeCtx:
    """Mirrors StreamingTaskMessageContext: __aenter__ opens (returns self with task_message set),
    close() closes. stream_update records the call.

    task_message is a real TaskMessage instance so that auto_send can use it
    as parent_task_message in StreamTaskMessageDelta without Pydantic validation errors.
    """

    def __init__(self, sink, content_type, initial_content):
        self.sink = sink
        self.content_type = content_type
        # Real TaskMessage so StreamTaskMessageDelta(parent_task_message=...) passes validation
        self.task_message = TaskMessage(id="msg-1", task_id="task1", content=initial_content)

    async def __aenter__(self):
        self.sink.append(("open", self.content_type))
        return self

    async def __aexit__(self, *a):
        # __aexit__ delegates to close in the real impl; keep for safety
        await self.close()
        return False

    async def close(self):
        self.sink.append(("close", self.content_type))

    async def stream_update(self, update):
        self.sink.append(("update", update))
        return update


class _FakeStreaming:
    """Mirrors StreamingService: streaming_task_message_context returns a context object."""

    def __init__(self):
        self.sink = []
        self.recorded_created_at: list[datetime | None] = []

    def streaming_task_message_context(self, task_id, initial_content, streaming_mode="coalesced", created_at=None):
        ctype = getattr(initial_content, "type", None)
        self.sink.append(("ctx", ctype))
        self.recorded_created_at.append(created_at)
        return _FakeCtx(self.sink, ctype, initial_content)


async def _gen(events):
    for e in events:
        yield e


# ---------------------------------------------------------------------------
# Test 1: text streaming — open, stream deltas, close; return accumulated text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_send_streams_text_and_returns_final_text():
    streaming = _FakeStreaming()
    events = [
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=TextDelta(type="text", text_delta="Hel"),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=TextDelta(type="text", text_delta="lo"),
        ),
        StreamTaskMessageDone(type="done", index=0),
    ]
    result = await auto_send(_gen(events), task_id="task1", tracer=None, streaming=streaming)

    assert result.final_text == "Hello"

    kinds = [s[0] for s in streaming.sink]
    # A context was created for the text content
    assert kinds[0] == "ctx"
    # It was opened and closed
    assert "open" in kinds
    assert "close" in kinds
    # Exactly two updates were streamed (one per delta)
    updates = [s for s in streaming.sink if s[0] == "update"]
    assert len(updates) == 2


# ---------------------------------------------------------------------------
# Test 2: tool_request Full + tool_response Full — each posts one full message
# (open context with the content, no deltas, close immediately)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_send_posts_full_tool_messages():
    streaming = _FakeStreaming()
    events = [
        # Two Full events post two messages (open+close immediately, no deltas).
        StreamTaskMessageFull(
            type="full",
            index=0,
            content=ToolRequestContent(
                type="tool_request",
                author="agent",
                tool_call_id="c1",
                name="Bash",
                arguments={"cmd": "ls"},
            ),
        ),
        StreamTaskMessageFull(
            type="full",
            index=1,
            content=ToolResponseContent(
                type="tool_response",
                author="agent",
                tool_call_id="c1",
                name="Bash",
                content="file.py",
            ),
        ),
    ]
    result = await auto_send(_gen(events), task_id="task1", tracer=None, streaming=streaming)

    assert result.final_text == ""

    # Each Full event opens and closes exactly one context.
    ctx_events = [s for s in streaming.sink if s[0] == "ctx"]
    assert len(ctx_events) == 2
    content_types = [s[1] for s in ctx_events]
    assert content_types == ["tool_request", "tool_response"]

    # Each context is opened and closed
    opens = [s for s in streaming.sink if s[0] == "open"]
    closes = [s for s in streaming.sink if s[0] == "close"]
    assert len(opens) == 2
    assert len(closes) == 2

    # No stream_update calls (full messages have no deltas)
    updates = [s for s in streaming.sink if s[0] == "update"]
    assert len(updates) == 0


# ---------------------------------------------------------------------------
# Test 3: tracing — spans are derived and handed to the tracer
# ---------------------------------------------------------------------------


class _RecordTracing:
    def __init__(self):
        self.started, self.ended = [], []

    async def start_span(self, *, trace_id, name, input=None, parent_id=None, data=None, task_id=None):
        self.started.append(name)
        return _types.SimpleNamespace()

    async def end_span(self, *, trace_id, span):
        self.ended.append(getattr(span, "output", None))


@pytest.mark.asyncio
async def test_auto_send_derives_tool_spans_via_tracer():
    fake_tracing = _RecordTracing()
    tracer = SpanTracer(trace_id="t", parent_span_id="p", tracing=fake_tracing)
    streaming = _FakeStreaming()

    events = [
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=ToolRequestContent(
                type="tool_request",
                author="agent",
                tool_call_id="c1",
                name="Bash",
                arguments={},
            ),
        ),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageFull(
            type="full",
            index=1,
            content=ToolResponseContent(
                type="tool_response",
                author="agent",
                tool_call_id="c1",
                name="Bash",
                content="ok",
            ),
        ),
    ]

    result = await auto_send(_gen(events), task_id="task1", tracer=tracer, streaming=streaming)

    assert result.final_text == ""
    assert fake_tracing.started == ["Bash"]
    assert fake_tracing.ended == ["ok"]


# ---------------------------------------------------------------------------
# Test 4: text followed by a tool Full — text context is closed before Full
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_send_closes_text_context_before_full_message():
    streaming = _FakeStreaming()
    events = [
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=TextDelta(type="text", text_delta="Hi"),
        ),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageFull(
            type="full",
            index=1,
            content=ToolRequestContent(
                type="tool_request",
                author="agent",
                tool_call_id="c2",
                name="read_file",
                arguments={},
            ),
        ),
    ]
    result = await auto_send(_gen(events), task_id="task1", tracer=None, streaming=streaming)
    assert result.final_text == "Hi"

    # Verify ordering: text ctx opens, updates, closes; then tool_request ctx opens, closes
    event_sequence = [(s[0], s[1]) for s in streaming.sink]
    text_open_idx = next(i for i, s in enumerate(event_sequence) if s == ("open", "text"))
    text_close_idx = next(i for i, s in enumerate(event_sequence) if s == ("close", "text"))
    tool_open_idx = next(i for i, s in enumerate(event_sequence) if s == ("open", "tool_request"))
    assert text_open_idx < text_close_idx < tool_open_idx


# ---------------------------------------------------------------------------
# Test 5: midstream error — propagates AND the open context is closed (finally)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_context_closed_on_midstream_error():
    streaming = _FakeStreaming()

    async def _exploding_gen():
        yield StreamTaskMessageStart(
            type="start",
            index=0,
            content=TextContent(type="text", author="agent", content=""),
        )
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await auto_send(_exploding_gen(), task_id="task1", tracer=None, streaming=streaming)

    # The text context that was opened mid-stream was closed by the finally block.
    assert ("open", "text") in [(s[0], s[1]) for s in streaming.sink]
    assert ("close", "text") in [(s[0], s[1]) for s in streaming.sink]


# ---------------------------------------------------------------------------
# Test 6: streamed tool_request delivered (AGX1-377 core)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_send_streams_tool_request():
    """A Start(ToolRequestContent) MUST open a streaming context (AGX1-377)."""
    streaming = _FakeStreaming()
    events = [
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=ToolRequestContent(
                type="tool_request",
                author="agent",
                tool_call_id="c_tool",
                name="Bash",
                arguments={},
            ),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=ToolRequestDelta(
                type="tool_request",
                tool_call_id="c_tool",
                name="Bash",
                arguments_delta='{"cmd": "ls"}',
            ),
        ),
        StreamTaskMessageDone(type="done", index=0),
    ]
    result = await auto_send(_gen(events), task_id="task1", tracer=None, streaming=streaming)

    assert result.final_text == ""

    ctx_events = [s for s in streaming.sink if s[0] == "ctx"]
    assert len(ctx_events) == 1
    assert ctx_events[0][1] == "tool_request"

    opens = [s for s in streaming.sink if s[0] == "open"]
    closes = [s for s in streaming.sink if s[0] == "close"]
    assert len(opens) == 1
    assert len(closes) == 1

    updates = [s for s in streaming.sink if s[0] == "update"]
    assert len(updates) == 1


# ---------------------------------------------------------------------------
# Test 7: interleaved indexes route correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_send_interleaved_indexes_route_correctly():
    """Deltas must be routed to the correct index-keyed context."""
    streaming = _FakeStreaming()
    events = [
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageStart(
            type="start",
            index=1,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=TextDelta(type="text", text_delta="A"),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=1,
            delta=TextDelta(type="text", text_delta="B"),
        ),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageDone(type="done", index=1),
    ]
    result = await auto_send(_gen(events), task_id="task1", tracer=None, streaming=streaming)

    ctx_events = [s for s in streaming.sink if s[0] == "ctx"]
    assert len(ctx_events) == 2

    opens = [s for s in streaming.sink if s[0] == "open"]
    assert len(opens) == 2

    updates = [s for s in streaming.sink if s[0] == "update"]
    assert len(updates) == 2

    update_deltas = [s[1].delta for s in streaming.sink if s[0] == "update"]
    text_deltas = [d.text_delta for d in update_deltas if isinstance(d, TextDelta)]
    assert set(text_deltas) == {"A", "B"}


# ---------------------------------------------------------------------------
# Test 8: final_text returns last text segment for multi-step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_send_final_text_last_segment():
    """final_text must be the LAST text segment, not accumulated across all turns."""
    streaming = _FakeStreaming()
    events = [
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=TextDelta(type="text", text_delta="First"),
        ),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageStart(
            type="start",
            index=1,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=1,
            delta=TextDelta(type="text", text_delta="Second"),
        ),
        StreamTaskMessageDone(type="done", index=1),
    ]
    result = await auto_send(_gen(events), task_id="task1", tracer=None, streaming=streaming)
    assert result.final_text == "Second"


# ---------------------------------------------------------------------------
# Test 9: Full(TextContent) contributes to final_text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_send_full_text_content_sets_final_text():
    """A Full(TextContent) must contribute its text to final_text."""
    streaming = _FakeStreaming()
    events = [
        StreamTaskMessageFull(
            type="full",
            index=0,
            content=TextContent(type="text", author="agent", content="hello"),
        ),
    ]
    result = await auto_send(_gen(events), task_id="task1", tracer=None, streaming=streaming)
    assert result.final_text == "hello"


# ---------------------------------------------------------------------------
# Test 10: created_at is forwarded to streaming context (AGX1-378)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_send_created_at_forwarded():
    """created_at must be forwarded to every streaming_task_message_context call."""
    streaming = _FakeStreaming()
    dt = datetime(2025, 1, 15, 12, 0, 0)
    events = [
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageFull(
            type="full",
            index=1,
            content=ToolRequestContent(
                type="tool_request",
                author="agent",
                tool_call_id="c_ts",
                name="Bash",
                arguments={},
            ),
        ),
    ]
    await auto_send(_gen(events), task_id="task1", tracer=None, streaming=streaming, created_at=dt)

    assert all(ts == dt for ts in streaming.recorded_created_at)
