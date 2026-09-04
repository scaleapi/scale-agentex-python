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
from agentex.lib.adk._modules._pydantic_ai_turn import stream_pydantic_ai_events

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

    def streaming_task_message_context(
        self, *, task_id: str, initial_content: Any, streaming_mode: str = "coalesced", created_at: Any = None
    ) -> FakeContext:
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
    async def test_tool_call_opens_streaming_context_with_identity(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """Tool requests are delivered as a streaming context (Start+Delta+Done).

        auto_send delivers streamed tool-request messages natively
        (Start+ToolRequestDelta+Done). The streaming context is opened
        at the Start event with the initial ToolRequestContent (tool_call_id +
        name + empty arguments), argument tokens are streamed as deltas, and the
        context is closed on Done.

        This test uses a realistic pydantic-ai event sequence: args arrive as a
        PartDeltaEvent fragment (the way OpenAI/Anthropic actually stream JSON
        tool-call arguments).
        """
        from pydantic_ai.messages import ToolCallPartDelta

        from agentex.types.tool_request_delta import ToolRequestDelta

        streaming, messages = fake_adk
        events = [
            PartStartEvent(
                index=1,
                part=ToolCallPart(tool_name="get_weather", args=None, tool_call_id="c1"),
            ),
            # Realistic: args arrive as delta tokens (JSON string fragments).
            PartDeltaEvent(
                index=1,
                delta=ToolCallPartDelta(args_delta='{"city":"Paris"}'),
            ),
            PartEndEvent(
                index=1,
                part=ToolCallPart(tool_name="get_weather", args='{"city":"Paris"}', tool_call_id="c1"),
            ),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        # AGX1-373: tool messages arrive via streaming_task_message_context.
        assert messages.created == [], "adk.messages.create must not be called"
        assert len(streaming.contexts) == 1, "tool_request opens a streaming context"
        ctx = streaming.contexts[0]
        assert ctx.closed is True
        content = ctx.initial_content
        assert isinstance(content, ToolRequestContent)
        assert content.tool_call_id == "c1"
        assert content.name == "get_weather"
        assert content.author == "agent"
        # Streamed shape: initial_content has empty args (args come via delta)
        assert content.arguments == {}
        # The arg delta is delivered as a stream_update
        assert len(ctx.updates) == 1
        assert isinstance(ctx.updates[0].delta, ToolRequestDelta)
        assert ctx.updates[0].delta.arguments_delta == '{"city":"Paris"}'

    async def test_tool_call_with_dict_args_passes_through(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """When args arrive pre-populated as a dict in PartStart, they're in initial_content."""
        streaming, messages = fake_adk
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

        # AGX1-373: tool messages via streaming_task_message_context
        assert messages.created == []
        assert len(streaming.contexts) == 1
        # Dict args present at PartStart land directly in initial_content.arguments
        assert streaming.contexts[0].initial_content.arguments == {"q": "weather"}
        assert streaming.contexts[0].updates == [], "no delta for pre-populated dict args"

    async def test_tool_call_with_invalid_json_args_surfaces_raw(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """Malformed JSON arg delta is surfaced as a ToolRequestDelta with the raw string.

        The argument delta is delivered as-is by auto_send; the client-side
        accumulator or the streaming backend handles malformed JSON gracefully.

        Parts-manager invariant: PartEnd.part is the accumulated snapshot; real
        pydantic-ai conveys args via PartStart + PartDeltaEvent, so a
        PartStart(None)+PartEnd(json) with no delta is not realizable.
        """
        from pydantic_ai.messages import ToolCallPartDelta

        from agentex.types.tool_request_delta import ToolRequestDelta

        streaming, messages = fake_adk
        events = [
            PartStartEvent(
                index=0,
                part=ToolCallPart(tool_name="t", args=None, tool_call_id="c"),
            ),
            # Malformed JSON arrives as a delta token.
            PartDeltaEvent(
                index=0,
                delta=ToolCallPartDelta(args_delta="not-json{"),
            ),
            PartEndEvent(
                index=0,
                part=ToolCallPart(tool_name="t", args="not-json{", tool_call_id="c"),
            ),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        # AGX1-373: tool messages via streaming_task_message_context
        assert messages.created == []
        assert len(streaming.contexts) == 1
        ctx = streaming.contexts[0]
        # Initial content has empty args (args come via delta)
        assert ctx.initial_content.arguments == {}
        # The malformed JSON is surfaced verbatim in the ToolRequestDelta
        assert len(ctx.updates) == 1
        assert isinstance(ctx.updates[0].delta, ToolRequestDelta)
        assert ctx.updates[0].delta.arguments_delta == "not-json{"

    async def test_tool_call_with_none_args_defaults_to_empty_dict(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        streaming, messages = fake_adk
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

        # AGX1-373: tool messages via streaming_task_message_context
        assert messages.created == []
        assert len(streaming.contexts) == 1
        assert streaming.contexts[0].initial_content.arguments == {}
        assert streaming.contexts[0].updates == [], "no delta when args are absent"


class TestToolResult:
    async def test_tool_return_emits_full_tool_response_message(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        # AGX1-373: tool responses arrive via streaming_task_message_context
        # (open+close pair), NOT via adk.messages.create.
        streaming, messages = fake_adk
        events = [
            FunctionToolResultEvent(
                part=ToolReturnPart(tool_name="get_weather", content="Sunny, 72F", tool_call_id="c1"),
            ),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert messages.created == [], "adk.messages.create must not be called after reimplementation"
        assert len(streaming.contexts) == 1
        ctx = streaming.contexts[0]
        assert ctx.closed is True
        content = ctx.initial_content
        assert isinstance(content, ToolResponseContent)
        assert content.tool_call_id == "c1"
        assert content.name == "get_weather"
        assert content.content == "Sunny, 72F"
        assert content.author == "agent"
        assert ctx.updates == [], "open+close only — no deltas for tool messages"

    async def test_tool_return_with_dict_content_preserves_structure(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """Regression: structured tool results (dict / list / pydantic model) must
        be preserved as structured data on ``ToolResponseContent.content``.

        The earlier ``str(content)`` path produced Python repr like
        ``"{'temp': 72, 'sky': 'clear'}"`` — invalid JSON, unreadable in the UI,
        and divergent from the sync converter which uses ``_tool_return_content``
        to return dicts as-is.
        """
        streaming, messages = fake_adk
        events = [
            FunctionToolResultEvent(
                part=ToolReturnPart(tool_name="t", content={"temp": 72, "sky": "clear"}, tool_call_id="c"),
            ),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        # AGX1-373: tool messages via streaming_task_message_context
        assert messages.created == []
        assert len(streaming.contexts) == 1
        out = streaming.contexts[0].initial_content.content
        assert out == {"temp": 72, "sky": "clear"}, (
            f"Expected the dict to survive verbatim; got {out!r}. "
            "If this is a Python repr string, the helper regressed to str(content)."
        )

    async def test_tool_return_with_pydantic_model_content_uses_model_dump(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """Pydantic model tool results must be serialized via ``model_dump()``,
        not ``str(model)``."""
        from pydantic import BaseModel

        class WeatherResult(BaseModel):
            temp: int
            sky: str

        streaming, messages = fake_adk
        events = [
            FunctionToolResultEvent(
                part=ToolReturnPart(
                    tool_name="t",
                    content=WeatherResult(temp=72, sky="clear"),
                    tool_call_id="c",
                ),
            ),
        ]
        await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        # AGX1-373: tool messages via streaming_task_message_context
        assert messages.created == []
        assert len(streaming.contexts) == 1
        out = streaming.contexts[0].initial_content.content
        assert out == {"temp": 72, "sky": "clear"}

    async def test_retry_prompt_part_surfaces_as_tool_response(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        streaming, messages = fake_adk
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

        # AGX1-373: tool messages via streaming_task_message_context
        assert messages.created == []
        assert len(streaming.contexts) == 1
        content = streaming.contexts[0].initial_content
        assert isinstance(content, ToolResponseContent)
        assert content.tool_call_id == "c1"
        # RetryPromptPart.content stringifies to the error description
        assert "bad arguments" in str(content.content)


class TestContextLifecycle:
    async def test_text_then_tool_then_text_uses_separate_contexts_in_order(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """End-to-end multi-step shape: text → tool call → tool result → more text.

        AGX1-373 envelope change: tool messages now arrive via
        streaming_task_message_context (open+close pairs) instead of
        adk.messages.create. All four message types open streaming contexts.
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

        # AGX1-373: all 4 messages (text, tool_request, tool_response, text)
        # arrive via streaming_task_message_context.
        assert messages.created == [], "adk.messages.create must not be called after reimplementation"
        assert len(streaming.contexts) == 4
        assert all(ctx.closed for ctx in streaming.contexts)

        text_ctxs = [ctx for ctx in streaming.contexts if isinstance(ctx.initial_content, TextContent)]
        tool_req_ctxs = [ctx for ctx in streaming.contexts if isinstance(ctx.initial_content, ToolRequestContent)]
        tool_resp_ctxs = [ctx for ctx in streaming.contexts if isinstance(ctx.initial_content, ToolResponseContent)]
        assert len(text_ctxs) == 2
        assert len(tool_req_ctxs) == 1
        assert len(tool_resp_ctxs) == 1

        assert _text_deltas(text_ctxs[0]) == ["Looking up..."]
        assert _text_deltas(text_ctxs[1]) == ["It's sunny."]

        # Tool content is preserved verbatim.
        assert tool_req_ctxs[0].initial_content.tool_call_id == "c1"
        assert tool_resp_ctxs[0].initial_content.tool_call_id == "c1"

        # Tool contexts carry no deltas (open+close only).
        assert tool_req_ctxs[0].updates == []
        assert tool_resp_ctxs[0].updates == []

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
        """A tool result arriving while a text context is open must close that context first.

        AGX1-373: the tool response itself now also opens a streaming context
        (open+close pair) rather than going through adk.messages.create.
        """
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
        # AGX1-373: tool response arrives via streaming_task_message_context
        assert messages.created == []
        assert len(streaming.contexts) == 2
        assert isinstance(streaming.contexts[1].initial_content, ToolResponseContent)


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


# ---------------------------------------------------------------------------
# Characterization test: lock the wire-level delivery shape for a representative
# pydantic-ai run (text + tool call + tool response + more text).
#
# Step 1 (CURRENT behavior): written against the original implementation.
# - Text/reasoning use adk.streaming.streaming_task_message_context.
# - Tool messages use adk.messages.create (FakeMessagesModule.created list).
# - Final text is the last text segment.
#
# Step 2 (POST-reimplementation on UnifiedEmitter / auto_send):
# The assertions in TestCharacterizeWireShapeNew (below) lock the new shape.
# Tool messages no longer go through adk.messages.create; they arrive via
# streaming_task_message_context open+close pairs (Start+Done envelope).
# This is the AGX1-373 accepted envelope change: logical content is identical.
# ---------------------------------------------------------------------------


class TestCharacterizeWireShape:
    """Characterization tests: lock the wire-level delivery shape after reimplementation.

    Uses FakeStreamingModule + FakeMessagesModule (the existing fake pair).

    AGX1-373 shape (post-reimplementation on UnifiedEmitter / auto_send):
    - Text/reasoning: streaming_task_message_context (open + deltas + close)
    - Tool messages: streaming_task_message_context (open+close, no deltas)
    - adk.messages.create is NOT called.
    - Final text == last text segment only.

    This class was first written to characterize the OLD shape (adk.messages.create
    for tool messages) and was updated post-reimplementation to reflect the new
    delivery channel. The logical content is identical; only the channel changed.
    """

    async def test_text_tool_text_new_wire_shape(
        self, fake_adk: tuple[FakeStreamingModule, FakeMessagesModule]
    ) -> None:
        """Representative run: text -> tool call -> tool response -> more text.

        Post-AGX1-373 delivery shape:
        - Four streaming contexts: text, tool_request, tool_response, text.
        - adk.messages.create NOT called.
        - Final text == "It's sunny." (last segment only, matching the
          multi-step convention).
        """
        from pydantic_ai.messages import ToolReturnPart

        streaming, messages = fake_adk
        events = [
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
            PartStartEvent(index=0, part=TextPart(content="")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="It's sunny.")),
            PartEndEvent(index=0, part=TextPart(content="It's sunny.")),
        ]

        final = await stream_pydantic_ai_events(_aiter(events), TASK_ID)

        assert final == "It's sunny.", "multi-step: only the last text segment is returned"

        # AGX1-373: all 4 messages arrive via streaming_task_message_context
        assert messages.created == []
        assert len(streaming.contexts) == 4
        assert all(ctx.closed for ctx in streaming.contexts)

        content_types = [type(ctx.initial_content).__name__ for ctx in streaming.contexts]
        assert content_types == [
            "TextContent",
            "ToolRequestContent",
            "ToolResponseContent",
            "TextContent",
        ]

        text_ctxs = [ctx for ctx in streaming.contexts if isinstance(ctx.initial_content, TextContent)]
        tool_req_ctxs = [ctx for ctx in streaming.contexts if isinstance(ctx.initial_content, ToolRequestContent)]
        tool_resp_ctxs = [ctx for ctx in streaming.contexts if isinstance(ctx.initial_content, ToolResponseContent)]

        assert _text_deltas(text_ctxs[0]) == ["Looking up..."]
        assert _text_deltas(text_ctxs[1]) == ["It's sunny."]
        assert tool_req_ctxs[0].initial_content.tool_call_id == "c1"
        assert tool_req_ctxs[0].initial_content.name == "get_weather"
        assert tool_req_ctxs[0].updates == []
        assert tool_resp_ctxs[0].initial_content.tool_call_id == "c1"
        assert tool_resp_ctxs[0].initial_content.content == "Sunny"
        assert tool_resp_ctxs[0].updates == []
