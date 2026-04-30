"""Tests for the streaming service: ``CoalescingBuffer``, merge helpers, and
``StreamingTaskMessageContext`` mode dispatch.

These exercise the in-process behavior of the streaming layer without hitting
Redis or any AgentEx HTTP endpoints — everything below the
``StreamingService.stream_update`` boundary is mocked.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.types.task_message_delta import (
    DataDelta,
    TextDelta,
    ToolRequestDelta,
    ToolResponseDelta,
    ReasoningSummaryDelta,
)
from agentex.types.task_message_update import StreamTaskMessageDelta
from agentex.lib.core.services.adk.streaming import (
    CoalescingBuffer,
    StreamingTaskMessageContext,
    _can_merge,
    _merge_pair,
    _delta_char_len,
    _merge_consecutive,
)


@pytest.fixture
def task_message() -> TaskMessage:
    return TaskMessage(
        id="m1",
        task_id="t1",
        content=TextContent(author="agent", content="", format="markdown"),
        streaming_status="IN_PROGRESS",
    )


def _text(tm: TaskMessage, s: str) -> StreamTaskMessageDelta:
    return StreamTaskMessageDelta(
        parent_task_message=tm,
        delta=TextDelta(type="text", text_delta=s),
        type="delta",
    )


def _reasoning_summary(tm: TaskMessage, idx: int, s: str) -> StreamTaskMessageDelta:
    return StreamTaskMessageDelta(
        parent_task_message=tm,
        delta=ReasoningSummaryDelta(
            type="reasoning_summary", summary_index=idx, summary_delta=s
        ),
        type="delta",
    )


async def _make_context(streaming_mode: str) -> tuple[StreamingTaskMessageContext, MagicMock, TaskMessage]:
    tm = TaskMessage(
        id="m1",
        task_id="t1",
        content=TextContent(author="agent", content="", format="markdown"),
        streaming_status="IN_PROGRESS",
    )
    svc = MagicMock()
    svc.stream_update = AsyncMock()
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=tm)
    client.messages.update = AsyncMock()
    ctx = StreamingTaskMessageContext(
        task_id="t1",
        initial_content=TextContent(author="agent", content="", format="markdown"),
        agentex_client=client,
        streaming_service=svc,
        streaming_mode=streaming_mode,  # type: ignore[arg-type]
    )
    await ctx.open()
    return ctx, svc, tm


class TestDeltaCharLen:
    def test_text_delta(self) -> None:
        assert _delta_char_len(TextDelta(type="text", text_delta="hello")) == 5

    def test_reasoning_summary_delta(self) -> None:
        assert (
            _delta_char_len(
                ReasoningSummaryDelta(
                    type="reasoning_summary", summary_index=0, summary_delta="abc"
                )
            )
            == 3
        )

    def test_none_delta_is_zero(self) -> None:
        assert _delta_char_len(None) == 0

    def test_empty_string_delta(self) -> None:
        assert _delta_char_len(TextDelta(type="text", text_delta="")) == 0


class TestCanMerge:
    def test_same_text_type(self) -> None:
        a = TextDelta(type="text", text_delta="a")
        b = TextDelta(type="text", text_delta="b")
        assert _can_merge(a, b) is True

    def test_different_types_never_merge(self) -> None:
        text = TextDelta(type="text", text_delta="a")
        data = DataDelta(type="data", data_delta="b")
        assert _can_merge(text, data) is False

    def test_reasoning_summary_same_index_merges(self) -> None:
        a = ReasoningSummaryDelta(type="reasoning_summary", summary_index=0, summary_delta="x")
        b = ReasoningSummaryDelta(type="reasoning_summary", summary_index=0, summary_delta="y")
        assert _can_merge(a, b) is True

    def test_reasoning_summary_different_index_blocks_merge(self) -> None:
        a = ReasoningSummaryDelta(type="reasoning_summary", summary_index=0, summary_delta="x")
        b = ReasoningSummaryDelta(type="reasoning_summary", summary_index=1, summary_delta="y")
        assert _can_merge(a, b) is False

    def test_tool_request_same_call_id_merges(self) -> None:
        a = ToolRequestDelta(type="tool_request", tool_call_id="c1", name="t", arguments_delta="{")
        b = ToolRequestDelta(type="tool_request", tool_call_id="c1", name="t", arguments_delta="}")
        assert _can_merge(a, b) is True

    def test_tool_request_different_call_id_blocks_merge(self) -> None:
        a = ToolRequestDelta(type="tool_request", tool_call_id="c1", name="t", arguments_delta="{")
        b = ToolRequestDelta(type="tool_request", tool_call_id="c2", name="t", arguments_delta="}")
        assert _can_merge(a, b) is False


class TestMergePair:
    def test_text_concatenates(self) -> None:
        merged = _merge_pair(
            TextDelta(type="text", text_delta="Hello "),
            TextDelta(type="text", text_delta="world"),
        )
        assert isinstance(merged, TextDelta)
        assert merged.text_delta == "Hello world"

    def test_reasoning_summary_concatenates_and_keeps_index(self) -> None:
        merged = _merge_pair(
            ReasoningSummaryDelta(
                type="reasoning_summary", summary_index=2, summary_delta="hello "
            ),
            ReasoningSummaryDelta(
                type="reasoning_summary", summary_index=2, summary_delta="world"
            ),
        )
        assert isinstance(merged, ReasoningSummaryDelta)
        assert merged.summary_index == 2
        assert merged.summary_delta == "hello world"

    def test_tool_response_concatenates_and_keeps_call_id(self) -> None:
        merged = _merge_pair(
            ToolResponseDelta(
                type="tool_response", tool_call_id="c1", name="t", content_delta="part1 "
            ),
            ToolResponseDelta(
                type="tool_response", tool_call_id="c1", name="t", content_delta="part2"
            ),
        )
        assert isinstance(merged, ToolResponseDelta)
        assert merged.tool_call_id == "c1"
        assert merged.content_delta == "part1 part2"

    def test_handles_none_string_fields(self) -> None:
        """Pydantic allows the *_delta fields to be None; merge must coerce to empty."""
        merged = _merge_pair(
            TextDelta(type="text", text_delta=None),
            TextDelta(type="text", text_delta="late"),
        )
        assert isinstance(merged, TextDelta)
        assert merged.text_delta == "late"


class TestMergeConsecutive:
    def test_pure_text_collapses_to_one(self, task_message: TaskMessage) -> None:
        deltas = [_text(task_message, s) for s in ["Hello", " ", "world", "!"]]
        merged = _merge_consecutive(deltas)
        assert len(merged) == 1
        assert merged[0].delta is not None
        assert isinstance(merged[0].delta, TextDelta)
        assert merged[0].delta.text_delta == "Hello world!"

    def test_empty_input_returns_empty_list(self) -> None:
        assert _merge_consecutive([]) == []

    def test_single_delta_passes_through(self, task_message: TaskMessage) -> None:
        deltas = [_text(task_message, "lone")]
        merged = _merge_consecutive(deltas)
        assert len(merged) == 1
        assert merged[0] is deltas[0]  # same object, no merge happened

    def test_cross_channel_order_preserved_for_reasoning(
        self, task_message: TaskMessage
    ) -> None:
        """Consecutive same-(type, index) merges; distinct channels never reorder."""
        deltas = [
            _reasoning_summary(task_message, 0, "Let me "),
            _reasoning_summary(task_message, 0, "think..."),
            _reasoning_summary(task_message, 1, "Maybe "),
            _reasoning_summary(task_message, 0, " Actually,"),
            _reasoning_summary(task_message, 0, " yes."),
        ]
        merged = _merge_consecutive(deltas)
        # Three groups: idx=0 run, idx=1 single, idx=0 run again — order preserved.
        assert len(merged) == 3
        assert merged[0].delta is not None and isinstance(
            merged[0].delta, ReasoningSummaryDelta
        )
        assert merged[1].delta is not None and isinstance(
            merged[1].delta, ReasoningSummaryDelta
        )
        assert merged[2].delta is not None and isinstance(
            merged[2].delta, ReasoningSummaryDelta
        )
        assert merged[0].delta.summary_index == 0
        assert merged[0].delta.summary_delta == "Let me think..."
        assert merged[1].delta.summary_index == 1
        assert merged[1].delta.summary_delta == "Maybe "
        assert merged[2].delta.summary_index == 0
        assert merged[2].delta.summary_delta == " Actually, yes."

    def test_per_channel_concat_matches_per_token_semantics(
        self, task_message: TaskMessage
    ) -> None:
        """Reconstructing per-channel content from the merged stream must match
        what a per-token consumer would have seen."""
        deltas = [
            _reasoning_summary(task_message, 0, "Hel"),
            _reasoning_summary(task_message, 0, "lo"),
            _reasoning_summary(task_message, 1, "World"),
            _reasoning_summary(task_message, 0, "!"),
        ]
        merged = _merge_consecutive(deltas)

        per_index: dict[int, str] = {}
        for u in merged:
            d = u.delta
            assert isinstance(d, ReasoningSummaryDelta)
            per_index[d.summary_index] = per_index.get(d.summary_index, "") + (
                d.summary_delta or ""
            )

        assert per_index == {0: "Hello!", 1: "World"}


class TestCoalescingBufferTimeWindow:
    @pytest.mark.asyncio
    async def test_first_delta_flushes_immediately(
        self, task_message: TaskMessage
    ) -> None:
        """The first-delta-immediate optimization should trip a flush in <=20ms,
        well below the 50ms time window, so consumers see ``something started``."""
        flushed: list[StreamTaskMessageDelta] = []

        async def on_flush(u: StreamTaskMessageDelta) -> None:
            flushed.append(u)

        buf = CoalescingBuffer(on_flush=on_flush)
        buf.start()
        try:
            await buf.add(_text(task_message, "hi"))
            # Give the ticker a single tick to drain the signal.
            await asyncio.sleep(0.020)
            assert len(flushed) == 1
            assert flushed[0].delta is not None and isinstance(
                flushed[0].delta, TextDelta
            )
            assert flushed[0].delta.text_delta == "hi"
        finally:
            await buf.close()

    @pytest.mark.asyncio
    async def test_size_threshold_triggers_early_flush(
        self, task_message: TaskMessage
    ) -> None:
        """Adding more than MAX_BUFFERED_CHARS in one shot should flush within
        a single asyncio tick, well before the 50ms timer would fire."""
        flushed: list[StreamTaskMessageDelta] = []

        async def on_flush(u: StreamTaskMessageDelta) -> None:
            flushed.append(u)

        buf = CoalescingBuffer(on_flush=on_flush)
        buf.start()
        try:
            # Burn the first-delta-immediate slot so we're on the steady-state path.
            await buf.add(_text(task_message, "x"))
            await asyncio.sleep(0.020)
            flushed.clear()

            # Now add 200 chars in one delta — well over MAX_BUFFERED_CHARS=128.
            await buf.add(_text(task_message, "A" * 200))
            await asyncio.sleep(0.010)  # half the timer interval; only size can fire here
            assert len(flushed) == 1
            assert flushed[0].delta is not None and isinstance(
                flushed[0].delta, TextDelta
            )
            assert flushed[0].delta.text_delta == "A" * 200
        finally:
            await buf.close()

    @pytest.mark.asyncio
    async def test_subsequent_deltas_coalesce_within_window(
        self, task_message: TaskMessage
    ) -> None:
        """Three small deltas added inside one timer window should publish as
        one merged delta (after the initial first-flush burns)."""
        flushed: list[StreamTaskMessageDelta] = []

        async def on_flush(u: StreamTaskMessageDelta) -> None:
            flushed.append(u)

        buf = CoalescingBuffer(on_flush=on_flush)
        buf.start()
        try:
            await buf.add(_text(task_message, "first"))  # immediate flush
            await asyncio.sleep(0.020)
            flushed.clear()

            for chunk in ("ab", "cd", "ef"):
                await buf.add(_text(task_message, chunk))
            # Wait past the 50ms window so the timer fires.
            await asyncio.sleep(0.080)
            # All three small deltas merge into a single publish.
            assert len(flushed) == 1
            assert flushed[0].delta is not None and isinstance(
                flushed[0].delta, TextDelta
            )
            assert flushed[0].delta.text_delta == "abcdef"
        finally:
            await buf.close()


class TestCoalescingBufferClose:
    @pytest.mark.asyncio
    async def test_close_drains_remaining_buffered_items(
        self, task_message: TaskMessage
    ) -> None:
        """Items added after the last timer tick must still flush before close()
        completes — the persisted message body and the stream contract both
        require it."""
        flushed: list[StreamTaskMessageDelta] = []

        async def on_flush(u: StreamTaskMessageDelta) -> None:
            flushed.append(u)

        buf = CoalescingBuffer(on_flush=on_flush)
        buf.start()
        await buf.add(_text(task_message, "first"))  # immediate
        await asyncio.sleep(0.020)
        flushed.clear()

        # Add an item and immediately close — too fast for the 50ms timer.
        await buf.add(_text(task_message, "last"))
        await buf.close()

        assert len(flushed) == 1
        assert flushed[0].delta is not None and isinstance(flushed[0].delta, TextDelta)
        assert flushed[0].delta.text_delta == "last"

    @pytest.mark.asyncio
    async def test_close_when_idle_is_safe(self, task_message: TaskMessage) -> None:
        """``close()`` with no buffered items must not raise."""
        buf = CoalescingBuffer(on_flush=AsyncMock())
        buf.start()
        await buf.close()  # no items, no signal, just exit cleanly

    @pytest.mark.asyncio
    async def test_add_after_close_is_noop(self, task_message: TaskMessage) -> None:
        """Defensive: ``add`` after ``close`` must silently do nothing rather
        than raise. Real flows shouldn't hit this but tests racing close()
        should not blow up."""
        flushed: list[StreamTaskMessageDelta] = []

        async def on_flush(u: StreamTaskMessageDelta) -> None:
            flushed.append(u)

        buf = CoalescingBuffer(on_flush=on_flush)
        buf.start()
        await buf.close()
        # Fully drained and closed; this should silently no-op.
        await buf.add(_text(task_message, "after"))
        assert flushed == []


class TestCoalescingBufferCancelDuringFlush:
    @pytest.mark.asyncio
    async def test_cancel_during_flush_recovers_remaining_items(
        self, task_message: TaskMessage
    ) -> None:
        """Regression: when ``close()`` cancels the ticker mid-flush, items in
        the local ``drained`` list must be re-enqueued so the final drain in
        ``close()`` can recover them. Otherwise the last coalesced batch is
        silently dropped — visible to consumers as a truncated stream.
        """
        flushed: list[StreamTaskMessageDelta] = []
        first_started = asyncio.Event()
        first_continue = asyncio.Event()

        async def slow_flush(u: StreamTaskMessageDelta) -> None:
            flushed.append(u)
            if len(flushed) == 1:
                first_started.set()
                # Block the first publish until the test releases it. This
                # guarantees the cancellation lands inside the flush loop.
                await first_continue.wait()

        buf = CoalescingBuffer(on_flush=slow_flush)
        buf.start()
        # Add five items quickly; they all land in self._buf and the ticker
        # will drain them as one merged batch.
        for i in range(5):
            await buf.add(_text(task_message, f"chunk{i}"))

        await asyncio.wait_for(first_started.wait(), timeout=2.0)
        # Trigger close() while the first flush is blocked, then release it.
        close_task = asyncio.create_task(buf.close())
        first_continue.set()
        await close_task

        # All five chunks must appear at least once across all publishes.
        # (The first-flushed item may duplicate; that's the documented
        # trade-off — duplicate > silent loss.)
        full = "".join(
            u.delta.text_delta or ""
            for u in flushed
            if isinstance(u.delta, TextDelta)
        )
        for i in range(5):
            assert f"chunk{i}" in full, (
                f"chunk{i} missing — silent data loss across cancel-during-flush boundary. "
                f"flushed payloads: {[u.delta.text_delta for u in flushed if isinstance(u.delta, TextDelta)]}"
            )


class TestStreamingTaskMessageContextModes:
    @pytest.mark.asyncio
    async def test_off_mode_skips_publishes_but_persists_full_content(self) -> None:
        ctx, svc, tm = await _make_context("off")
        svc.stream_update.reset_mock()
        for chunk in ("Hello", " ", "world"):
            await ctx.stream_update(_text(tm, chunk))
        # Plenty of time for any background ticker — none should exist.
        await asyncio.sleep(0.080)
        assert svc.stream_update.call_count == 0, (
            "off mode must publish zero per-delta updates"
        )

        await ctx.close()
        # The persisted message body must still contain the full assembled text,
        # because the accumulator was fed even when publishing was suppressed.
        update_kwargs = ctx._agentex_client.messages.update.call_args.kwargs
        assert update_kwargs["content"]["content"] == "Hello world"

    @pytest.mark.asyncio
    async def test_per_token_mode_publishes_each_delta_immediately(self) -> None:
        ctx, svc, tm = await _make_context("per_token")
        svc.stream_update.reset_mock()
        for chunk in ("a", "b", "c"):
            await ctx.stream_update(_text(tm, chunk))
        # Per-token mode must publish synchronously, no waiting required.
        assert svc.stream_update.call_count == 3
        await ctx.close()

    @pytest.mark.asyncio
    async def test_coalesced_mode_batches_and_persists_full_content(self) -> None:
        ctx, svc, tm = await _make_context("coalesced")
        svc.stream_update.reset_mock()
        for chunk in ("Hello", " ", "world", "!"):
            await ctx.stream_update(_text(tm, chunk))
        await ctx.close()

        # Assembled content is the union of all per-delta text.
        update_kwargs = ctx._agentex_client.messages.update.call_args.kwargs
        assert update_kwargs["content"]["content"] == "Hello world!"

        # Coalesced mode produces fewer publishes than per_token (4) but at
        # least the start + at least one delta + done.
        delta_publishes = [
            call
            for call in svc.stream_update.call_args_list
            if isinstance(call.args[0] if call.args else None, StreamTaskMessageDelta)
        ]
        assert len(delta_publishes) >= 1, "coalesced mode should publish at least one delta"
        assert len(delta_publishes) < 4, (
            "coalesced mode should batch at least some of the four chunks"
        )
