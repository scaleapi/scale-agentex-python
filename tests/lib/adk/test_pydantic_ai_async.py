"""Tests for the async Pydantic AI -> Agentex streaming helper.

Unlike the sync converter (which yields ``StreamTaskMessage*`` events for the
caller to forward over HTTP), the async helper publishes deltas to Redis
through ``adk.streaming.streaming_task_message_context`` and full messages
through ``adk.messages.create``. These tests substitute both with in-memory
fakes so we can assert exactly what was published without touching Redis or
the AgentEx server.
"""

from __future__ import annotations

from typing import Any, AsyncIterator
from dataclasses import field, dataclass

import pytest
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
    ThinkingPartDelta,
    FunctionToolResultEvent,
)

from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import StreamTaskMessageDelta
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.types.reasoning_content_delta import ReasoningContentDelta
from agentex.lib.adk._modules._pydantic_ai_async import stream_pydantic_ai_events

TASK_ID = "task_test"


async def _aiter(events: list[Any]) -> AsyncIterator[Any]:
    for e in events:
        yield e


@dataclass
class FakeContext:
    """In-memory stand-in for ``StreamingTaskMessageContext``.

    Records the order of updates and whether ``close()`` was called. The
    helper drives this manually via ``__aenter__`` / ``close``, so we don't
    use it as an ``async with`` — we just track the calls.
    """

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
            raise AssertionError("stream_update called after close — helper closed the wrong context")
        self.updates.append(update)

    async def close(self) -> None:
        self.closed = True


class FakeStreamingModule:
    """Records every streaming context the helper opens, in order."""

    def __init__(self) -> None:
        self.contexts: list[FakeContext] = []

    def streaming_task_message_context(self, *, task_id: str, initial_content: Any) -> FakeContext:
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
    """Records every ``adk.messages.create`` call."""

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
    """Patches the lazy ``from agentex.lib import adk`` lookup inside the helper.

    Returns ``(streaming, messages)`` for assertions.
    """
    from agentex.lib import adk as adk_module

    streaming = FakeStreamingModule()
    messages = FakeMessagesModule()
    monkeypatch.setattr(adk_module, "streaming", streaming)
    monkeypatch.setattr(adk_module, "messages", messages)
    return streaming, messages


def _text_deltas(ctx: FakeContext) -> list[str]:
    out: list[str] = []
    for u in ctx.updates:
        if isinstance(u.delta, TextDelta):
            out.append(u.delta.text_delta or "")
    return out


def _reasoning_deltas(ctx: FakeContext) -> list[str]:
    out: list[str] = []
    for u in ctx.updates:
        if isinstance(u.delta, ReasoningContentDelta):
            out.append(u.delta.content_delta or "")
    return out


class TestTextStreaming:
    async def test_plain_text_opens_context_streams_deltas_and_closes(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        streaming, messages = fake_adk
        events = [
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Hello")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta=", ")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="world!")),
            PartEndEvent(index=0, part=TextPart(content="Hello, world!")),
        ]

        final = await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert len(streaming.contexts) == 1
        ctx = streaming.contexts[0]
        assert isinstance(ctx.initial_content, TextContent)
        assert ctx.initial_content.content == ""
        assert _text_deltas(ctx) == ["Hello", ", ", "world!"]
        assert ctx.closed is True, "PartEndEvent must close the streaming context"
        assert messages.created == [], "Plain text must not emit standalone messages"
        assert final == "Hello, world!"

    async def test_initial_content_in_part_start_is_streamed_as_delta(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """Pydantic AI sometimes packs the first chunk inside ``PartStartEvent.part.content``.

        Agentex renders only Delta events as the message body, so the helper
        must surface that initial chunk as a delta — otherwise the first token
        is invisible to the UI.
        """
        streaming, _ = fake_adk
        events = [
            PartStartEvent(index=0, part=TextPart(content="Already there")),
            PartEndEvent(index=0, part=TextPart(content="Already there")),
        ]
        final = await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        ctx = streaming.contexts[0]
        assert _text_deltas(ctx) == ["Already there"]
        assert final == "Already there"

    async def test_returns_only_last_text_segment_in_multi_step_run(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """Matches the documented contract / the LangGraph async helper's behavior."""
        streaming, _ = fake_adk
        events = [
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Looking up...")),
            PartEndEvent(index=0, part=TextPart(content="Looking up...")),
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="It's sunny.")),
            PartEndEvent(index=0, part=TextPart(content="It's sunny.")),
        ]
        final = await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert len(streaming.contexts) == 2, "Two text parts → two streaming contexts"
        assert all(ctx.closed for ctx in streaming.contexts)
        assert _text_deltas(streaming.contexts[0]) == ["Looking up..."]
        assert _text_deltas(streaming.contexts[1]) == ["It's sunny."]
        assert final == "It's sunny."


class TestThinkingStreaming:
    async def test_thinking_opens_reasoning_context_with_reasoning_deltas(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        streaming, _ = fake_adk
        events = [
            PartStartEvent(index=0, part=ThinkingPart(content="")),
            PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta="step 1...")),
            PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta=" step 2.")),
            PartEndEvent(index=0, part=ThinkingPart(content="step 1... step 2.")),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        ctx = streaming.contexts[0]
        assert isinstance(ctx.initial_content, ReasoningContent)
        assert _reasoning_deltas(ctx) == ["step 1...", " step 2."]
        assert ctx.closed is True

    async def test_thinking_initial_content_is_streamed_as_delta(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        streaming, _ = fake_adk
        events = [
            PartStartEvent(index=0, part=ThinkingPart(content="seed reasoning")),
            PartEndEvent(index=0, part=ThinkingPart(content="seed reasoning")),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        ctx = streaming.contexts[0]
        assert _reasoning_deltas(ctx) == ["seed reasoning"]

    async def test_empty_thinking_delta_is_skipped(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        streaming, _ = fake_adk
        events = [
            PartStartEvent(index=0, part=ThinkingPart(content="")),
            PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta=None)),
            PartEndEvent(index=0, part=ThinkingPart(content="")),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        ctx = streaming.contexts[0]
        assert _reasoning_deltas(ctx) == [], "Empty ThinkingPartDelta must not publish a zero-length reasoning delta"
        assert ctx.closed is True


class TestToolCallEmission:
    async def test_tool_call_emits_full_tool_request_message_on_part_end(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """Async helper uses Option A: tool requests are full messages, not delta streams."""
        streaming, messages = fake_adk
        events = [
            PartStartEvent(
                index=1,
                part=ToolCallPart(tool_name="get_weather", args=None, tool_call_id="c1"),
            ),
            PartEndEvent(
                index=1,
                part=ToolCallPart(tool_name="get_weather", args='{"city":"Paris"}', tool_call_id="c1"),
            ),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert streaming.contexts == [], "Tool calls do not open a streaming context"
        assert len(messages.created) == 1
        msg = messages.created[0]
        assert msg["task_id"] == TASK_ID
        content = msg["content"]
        assert isinstance(content, ToolRequestContent)
        assert content.tool_call_id == "c1"
        assert content.name == "get_weather"
        assert content.arguments == {"city": "Paris"}
        assert content.author == "agent"

    async def test_tool_call_with_dict_args_passes_through(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        _, messages = fake_adk
        events = [
            PartStartEvent(
                index=0,
                part=ToolCallPart(tool_name="search", args={"q": "weather"}, tool_call_id="c"),
            ),
            PartEndEvent(
                index=0,
                part=ToolCallPart(tool_name="search", args={"q": "weather"}, tool_call_id="c"),
            ),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert len(messages.created) == 1
        assert messages.created[0]["content"].arguments == {"q": "weather"}

    async def test_tool_call_with_invalid_json_args_surfaces_raw(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """Don't drop the tool call when the model emits malformed JSON args.

        The arguments field is preserved under ``_raw`` so the failure is
        visible to the UI rather than silently truncated.
        """
        _, messages = fake_adk
        events = [
            PartStartEvent(
                index=0,
                part=ToolCallPart(tool_name="t", args=None, tool_call_id="c"),
            ),
            PartEndEvent(
                index=0,
                part=ToolCallPart(tool_name="t", args="not-json{", tool_call_id="c"),
            ),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert len(messages.created) == 1
        assert messages.created[0]["content"].arguments == {"_raw": "not-json{"}

    async def test_tool_call_with_none_args_defaults_to_empty_dict(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        _, messages = fake_adk
        events = [
            PartStartEvent(
                index=0,
                part=ToolCallPart(tool_name="t", args=None, tool_call_id="c"),
            ),
            PartEndEvent(
                index=0,
                part=ToolCallPart(tool_name="t", args=None, tool_call_id="c"),
            ),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert len(messages.created) == 1
        assert messages.created[0]["content"].arguments == {}


class TestToolResult:
    async def test_tool_return_emits_full_tool_response_message(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        _, messages = fake_adk
        events = [
            FunctionToolResultEvent(
                part=ToolReturnPart(tool_name="get_weather", content="Sunny, 72F", tool_call_id="c1"),
            ),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert len(messages.created) == 1
        content = messages.created[0]["content"]
        assert isinstance(content, ToolResponseContent)
        assert content.tool_call_id == "c1"
        assert content.name == "get_weather"
        assert content.content == "Sunny, 72F"
        assert content.author == "agent"

    async def test_tool_return_with_non_string_content_stringifies(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        _, messages = fake_adk
        events = [
            FunctionToolResultEvent(
                part=ToolReturnPart(tool_name="t", content={"temp": 72, "sky": "clear"}, tool_call_id="c"),
            ),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        # The content is stringified; we just check the structured payload is
        # still readable from the result.
        out = messages.created[0]["content"].content
        assert "72" in out and "clear" in out

    async def test_retry_prompt_part_surfaces_as_tool_response(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        _, messages = fake_adk
        events = [
            FunctionToolResultEvent(
                part=RetryPromptPart(
                    content="bad arguments",
                    tool_name="get_weather",
                    tool_call_id="c1",
                ),
            ),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert len(messages.created) == 1
        content = messages.created[0]["content"]
        assert isinstance(content, ToolResponseContent)
        assert content.tool_call_id == "c1"
        # RetryPromptPart.content stringifies to the error description
        assert "bad arguments" in str(content.content)


class TestContextLifecycle:
    async def test_text_then_tool_then_text_uses_separate_contexts_in_order(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """End-to-end multi-step shape: text → tool call → tool result → more text.

        Each text/reasoning segment must get its own streaming context that is
        closed before the next one opens, and tool messages must interleave
        correctly via ``adk.messages.create``.
        """
        streaming, messages = fake_adk
        events = [
            # First model response: text + tool call.
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Looking up...")),
            PartEndEvent(index=0, part=TextPart(content="Looking up...")),
            PartStartEvent(
                index=1,
                part=ToolCallPart(tool_name="get_weather", args=None, tool_call_id="c1"),
            ),
            PartEndEvent(
                index=1,
                part=ToolCallPart(tool_name="get_weather", args="{}", tool_call_id="c1"),
            ),
            FunctionToolResultEvent(
                part=ToolReturnPart(tool_name="get_weather", content="Sunny", tool_call_id="c1"),
            ),
            # Second model response: more text.
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="It's sunny.")),
            PartEndEvent(index=0, part=TextPart(content="It's sunny.")),
        ]
        final = await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert len(streaming.contexts) == 2, "One context per text part — tool calls don't open streaming contexts"
        assert all(ctx.closed for ctx in streaming.contexts)
        assert _text_deltas(streaming.contexts[0]) == ["Looking up..."]
        assert _text_deltas(streaming.contexts[1]) == ["It's sunny."]

        # Two messages: tool request, then tool response — in that order.
        assert [type(m["content"]).__name__ for m in messages.created] == [
            "ToolRequestContent",
            "ToolResponseContent",
        ]
        assert messages.created[0]["content"].tool_call_id == "c1"
        assert messages.created[1]["content"].tool_call_id == "c1"
        assert final == "It's sunny."

    async def test_new_text_part_after_text_closes_previous(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """Defensive: two text parts in a row (same response) must not bleed deltas across contexts."""
        streaming, _ = fake_adk
        events = [
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="A")),
            PartStartEvent(index=1, part=TextPart(content="")),
            PartDeltaEvent(index=1, delta=TextPartDelta(content_delta="B")),
            PartEndEvent(index=1, part=TextPart(content="B")),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert len(streaming.contexts) == 2
        # First context was closed when the second TextPart started.
        assert streaming.contexts[0].closed is True
        assert _text_deltas(streaming.contexts[0]) == ["A"]
        assert _text_deltas(streaming.contexts[1]) == ["B"]

    async def test_reasoning_then_text_closes_reasoning_context(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """Switching from a thinking part to a text part must close the reasoning context."""
        streaming, _ = fake_adk
        events = [
            PartStartEvent(index=0, part=ThinkingPart(content="")),
            PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta="think")),
            PartStartEvent(index=1, part=TextPart(content="")),
            PartDeltaEvent(index=1, delta=TextPartDelta(content_delta="answer")),
            PartEndEvent(index=1, part=TextPart(content="answer")),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert len(streaming.contexts) == 2
        # Reasoning context closed before text opened.
        assert streaming.contexts[0].closed is True
        assert isinstance(streaming.contexts[0].initial_content, ReasoningContent)
        assert _reasoning_deltas(streaming.contexts[0]) == ["think"]
        assert isinstance(streaming.contexts[1].initial_content, TextContent)
        assert _text_deltas(streaming.contexts[1]) == ["answer"]

    async def test_tool_result_closes_any_open_streaming_context(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """A tool result arriving while a text context is open must close that context first."""
        streaming, messages = fake_adk
        events = [
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="thinking")),
            # No PartEndEvent — provider sends the tool result while text is "live".
            FunctionToolResultEvent(
                part=ToolReturnPart(tool_name="t", content="ok", tool_call_id="c"),
            ),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert streaming.contexts[0].closed is True, (
            "Helper must close any open streaming context before emitting a tool result message"
        )
        assert len(messages.created) == 1


class TestDeltaForOrphanIndexIgnored:
    async def test_part_delta_without_matching_start_is_ignored(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """A delta for an index we never saw a Start for must be a no-op, not a crash."""
        streaming, messages = fake_adk
        events = [
            PartDeltaEvent(index=99, delta=TextPartDelta(content_delta="orphan")),
        ]
        final = await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert streaming.contexts == []
        assert messages.created == []
        assert final == ""


class TestCleanupOnException:
    async def test_open_contexts_are_closed_on_iterator_failure(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """If the upstream Pydantic AI stream raises mid-flight, any open
        streaming context must still be closed — otherwise the Agentex
        ``messages.update(..., streaming_status="DONE")`` call never runs and
        the UI shows a perma-streaming message."""
        streaming, _ = fake_adk

        async def boom() -> AsyncIterator[Any]:
            yield PartStartEvent(index=0, part=TextPart(content=""))
            yield PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="partial"))
            raise RuntimeError("upstream provider exploded")

        with pytest.raises(RuntimeError, match="upstream provider exploded"):
            await stream_pydantic_ai_events(boom(), TASK_ID)

        assert streaming.contexts[0].closed is True
