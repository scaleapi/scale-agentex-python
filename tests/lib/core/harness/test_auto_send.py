"""Tests for auto_send delivery adapter.

The fake mirrors the real StreamingTaskMessageContext API exactly:
- streaming_task_message_context(...) returns a context object (synchronously)
- open the context via __aenter__ (returns self after creating the task message)
- stream deltas via ctx.stream_update(StreamTaskMessageDelta(...))
- close via ctx.close() (NOT __aexit__)

This mirrors _langgraph_async.py lines 62-78 and 100-127.
"""

import types as _types

import pytest

from agentex.lib.core.harness.auto_send import auto_send
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.types.task_message import TaskMessage
from agentex.types.task_message_update import (
    StreamTaskMessageStart,
    StreamTaskMessageDelta,
    StreamTaskMessageDone,
    StreamTaskMessageFull,
)
from agentex.types.text_content import TextContent
from agentex.types.task_message_delta import TextDelta
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
        self.task_message = TaskMessage(
            id="msg-1", task_id="task1", content=initial_content
        )

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

    def streaming_task_message_context(
        self, task_id, initial_content, streaming_mode="coalesced", created_at=None
    ):
        ctype = getattr(initial_content, "type", None)
        self.sink.append(("ctx", ctype))
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
            type="start", index=0,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageDelta(
            type="delta", index=0,
            delta=TextDelta(type="text", text_delta="Hel"),
        ),
        StreamTaskMessageDelta(
            type="delta", index=0,
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
        StreamTaskMessageFull(
            type="full", index=0,
            content=ToolRequestContent(
                type="tool_request", author="agent",
                tool_call_id="c1", name="Bash", arguments={"cmd": "ls"},
            ),
        ),
        StreamTaskMessageFull(
            type="full", index=1,
            content=ToolResponseContent(
                type="tool_response", author="agent",
                tool_call_id="c1", name="Bash", content="file.py",
            ),
        ),
    ]
    result = await auto_send(_gen(events), task_id="task1", tracer=None, streaming=streaming)

    assert result.final_text == ""

    # One context per Full event
    ctx_events = [s for s in streaming.sink if s[0] == "ctx"]
    assert len(ctx_events) == 2
    content_types = [s[1] for s in ctx_events]
    assert "tool_request" in content_types
    assert "tool_response" in content_types

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
            type="start", index=0,
            content=ToolRequestContent(
                type="tool_request", author="agent",
                tool_call_id="c1", name="Bash", arguments={},
            ),
        ),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageFull(
            type="full", index=1,
            content=ToolResponseContent(
                type="tool_response", author="agent",
                tool_call_id="c1", name="Bash", content="ok",
            ),
        ),
    ]

    result = await auto_send(
        _gen(events), task_id="task1", tracer=tracer, streaming=streaming
    )

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
            type="start", index=0,
            content=TextContent(type="text", author="agent", content=""),
        ),
        StreamTaskMessageDelta(
            type="delta", index=0,
            delta=TextDelta(type="text", text_delta="Hi"),
        ),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageFull(
            type="full", index=1,
            content=ToolRequestContent(
                type="tool_request", author="agent",
                tool_call_id="c2", name="read_file", arguments={},
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
