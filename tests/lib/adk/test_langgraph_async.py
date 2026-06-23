"""Characterization tests for stream_langgraph_events (unified surface).

These tests verify the behavior of ``stream_langgraph_events`` after it was
reimplemented on top of ``LangGraphTurn`` + ``UnifiedEmitter.auto_send_turn``
(Task 4). They serve as a contract test for the public signature.

Key behavioral notes (unified surface vs. old bespoke implementation):
- Tool calls/responses are posted via ``streaming_task_message_context`` (not
  ``adk.messages.create``); they appear as contexts with no stream_update calls.
- ``final_text`` accumulates ALL text across the turn (the old bespoke impl
  only returned the last text segment — behavior varied across models).

NOTE: langchain_core imports are deferred to test scope because conftest.py
stubs ``langchain_core.messages`` with MagicMock.
"""

from __future__ import annotations

import sys
from typing import Any
from dataclasses import field, dataclass

import pytest

from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import StreamTaskMessageDelta
from agentex.lib.adk._modules._langgraph_async import stream_langgraph_events

TASK_ID = "task-test"


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
# Fake streaming infrastructure (mirrors test_pydantic_ai_async.py pattern)
# ---------------------------------------------------------------------------


@dataclass
class FakeContext:
    initial_content: Any
    task_message: TaskMessage
    closed: bool = False
    updates: list[StreamTaskMessageDelta] = field(default_factory=list)

    async def __aenter__(self) -> "FakeContext":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        await self.close()
        return False

    async def stream_update(self, update: StreamTaskMessageDelta) -> None:
        if self.closed:
            raise AssertionError("stream_update called after close")
        self.updates.append(update)

    async def close(self) -> None:
        self.closed = True


class FakeStreamingModule:
    def __init__(self) -> None:
        self.contexts: list[FakeContext] = []

    def streaming_task_message_context(self, *, task_id: str, initial_content: Any, **kw: Any) -> FakeContext:
        tm = TaskMessage(
            id=f"m{len(self.contexts) + 1}",
            task_id=task_id,
            content=initial_content,
            streaming_status="IN_PROGRESS",
        )
        ctx = FakeContext(initial_content=initial_content, task_message=tm)
        self.contexts.append(ctx)
        return ctx


class FakeMessagesModule:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    async def create(self, *, task_id: str, content: Any) -> TaskMessage:
        self.created.append({"task_id": task_id, "content": content})
        return TaskMessage(
            id=f"created-{len(self.created)}",
            task_id=task_id,
            content=content,
            streaming_status="DONE",
        )


@pytest.fixture
def fake_adk(monkeypatch):
    from agentex.lib import adk as adk_module

    streaming = FakeStreamingModule()
    messages = FakeMessagesModule()
    monkeypatch.setattr(adk_module, "streaming", streaming)
    monkeypatch.setattr(adk_module, "messages", messages)
    return streaming, messages


def _make_stream(events: list[tuple[str, Any]]):
    async def _gen():
        for e in events:
            yield e

    return _gen()


def _text_deltas(ctx: FakeContext) -> list[str]:
    out: list[str] = []
    for u in ctx.updates:
        if isinstance(u.delta, TextDelta):
            out.append(u.delta.text_delta or "")
    return out


# ---------------------------------------------------------------------------
# Characterization tests (unified surface behavior)
# ---------------------------------------------------------------------------


class TestCharacterization:
    async def test_plain_text_streams_and_returns_final_text(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        from langchain_core.messages import AIMessage, AIMessageChunk

        streaming, messages = fake_adk
        chunk = AIMessageChunk(content="Hello, world!")
        ai_msg = AIMessage(content="Hello, world!")
        stream = _make_stream(
            [
                ("messages", (chunk, {})),
                ("updates", {"agent": {"messages": [ai_msg]}}),
            ]
        )

        final = await stream_langgraph_events(stream, TASK_ID)

        assert final == "Hello, world!"
        assert len(streaming.contexts) == 1
        ctx = streaming.contexts[0]
        assert isinstance(ctx.initial_content, TextContent)
        assert _text_deltas(ctx) == ["Hello, world!"]
        assert ctx.closed is True
        # Unified surface: no messages.create for text
        assert messages.created == []

    async def test_empty_stream_returns_empty_string(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        streaming, _ = fake_adk
        final = await stream_langgraph_events(_make_stream([]), TASK_ID)
        assert final == ""
        assert streaming.contexts == []

    async def test_tool_call_posted_via_streaming_context(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """Unified surface: tool calls go through streaming_task_message_context,
        not adk.messages.create. The context is opened and immediately closed
        (no deltas) so the initial_content is the tool request."""
        from langchain_core.messages import AIMessage

        streaming, messages = fake_adk
        tc = {"id": "call_1", "name": "get_weather", "args": {"city": "Paris"}}
        ai_msg = AIMessage(content="", tool_calls=[tc])
        stream = _make_stream([("updates", {"agent": {"messages": [ai_msg]}})])

        await stream_langgraph_events(stream, TASK_ID)

        # Unified surface: tool messages go via streaming_task_message_context
        assert len(streaming.contexts) == 1
        assert messages.created == [], "Unified surface uses streaming_task_message_context, not messages.create"

        from agentex.types.tool_request_content import ToolRequestContent

        content = streaming.contexts[0].initial_content
        assert isinstance(content, ToolRequestContent)
        assert content.tool_call_id == "call_1"
        assert content.name == "get_weather"
        assert content.arguments == {"city": "Paris"}
        # Full messages close immediately (no delta updates)
        assert streaming.contexts[0].closed is True
        assert streaming.contexts[0].updates == []

    async def test_tool_response_posted_via_streaming_context(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """Unified surface: tool responses go through streaming_task_message_context."""
        from langchain_core.messages import ToolMessage

        streaming, messages = fake_adk
        tool_msg = ToolMessage(content="Sunny, 72F", tool_call_id="call_1", name="get_weather")
        stream = _make_stream([("updates", {"tools": {"messages": [tool_msg]}})])

        await stream_langgraph_events(stream, TASK_ID)

        assert len(streaming.contexts) == 1
        assert messages.created == []

        from agentex.types.tool_response_content import ToolResponseContent

        content = streaming.contexts[0].initial_content
        assert isinstance(content, ToolResponseContent)
        assert content.tool_call_id == "call_1"
        assert content.name == "get_weather"
        assert content.content == "Sunny, 72F"
        assert streaming.contexts[0].closed is True

    async def test_multi_step_text_then_tool_then_text_last_segment(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """Unified surface: final_text uses last-segment semantics.

        auto_send resets final_text_parts when a new Start(TextContent) is seen,
        so multi-step turns (text -> tool -> text) return only the LAST text segment.
        Both text contexts are still opened and streamed to Redis; only the
        return value is last-segment. This matches stream_pydantic_ai_events.
        """
        from langchain_core.messages import AIMessage, ToolMessage, AIMessageChunk

        streaming, messages = fake_adk
        chunk1 = AIMessageChunk(content="Looking up...")
        ai_msg1 = AIMessage(content="Looking up...", tool_calls=[{"id": "c1", "name": "search", "args": {}}])
        tool_msg = ToolMessage(content="result", tool_call_id="c1", name="search")
        chunk2 = AIMessageChunk(content="Found it!")
        ai_msg2 = AIMessage(content="Found it!")

        stream = _make_stream(
            [
                ("messages", (chunk1, {})),
                ("updates", {"agent": {"messages": [ai_msg1]}}),
                ("updates", {"tools": {"messages": [tool_msg]}}),
                ("messages", (chunk2, {})),
                ("updates", {"agent": {"messages": [ai_msg2]}}),
            ]
        )

        final = await stream_langgraph_events(stream, TASK_ID)

        # Last segment only — first text segment is NOT in final_text
        assert final == "Found it!"
        # Two text streaming contexts (one per text segment) — both streamed to Redis
        text_ctxs = [c for c in streaming.contexts if isinstance(c.initial_content, TextContent)]
        assert len(text_ctxs) == 2
        assert all(ctx.closed for ctx in text_ctxs)
        # Tool request + tool response via streaming_task_message_context (not messages.create)
        assert messages.created == []

    async def test_context_closed_on_exception(self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]) -> None:
        from langchain_core.messages import AIMessageChunk

        streaming, _ = fake_adk

        async def _boom():
            chunk = AIMessageChunk(content="partial")
            yield ("messages", (chunk, {}))
            raise RuntimeError("upstream exploded")

        with pytest.raises(RuntimeError, match="upstream exploded"):
            await stream_langgraph_events(_boom(), TASK_ID)

        assert streaming.contexts[0].closed is True
