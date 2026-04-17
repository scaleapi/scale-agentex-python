from __future__ import annotations

import time
import uuid
import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from agentex.types.span import Span
from agentex.lib.core.tracing.span_queue import SpanEventType, AsyncSpanQueue, _SpanQueueItem


def _make_span(span_id: str | None = None) -> Span:
    return Span(
        id=span_id or str(uuid.uuid4()),
        name="test-span",
        start_time=datetime.now(UTC),
        trace_id="trace-1",
    )


def _make_processor(**overrides: AsyncMock) -> AsyncMock:
    proc = AsyncMock()
    proc.on_span_start = overrides.get("on_span_start", AsyncMock())
    proc.on_span_end = overrides.get("on_span_end", AsyncMock())
    return proc


class TestAsyncSpanQueueNonBlocking:
    async def test_enqueue_does_not_block(self):
        started = asyncio.Event()

        async def slow_start(span: Span) -> None:
            started.set()
            await asyncio.sleep(1.0)

        slow_processor = _make_processor(
            on_span_start=AsyncMock(side_effect=slow_start),
        )
        queue = AsyncSpanQueue()
        span = _make_span()

        start = time.monotonic()
        queue.enqueue(SpanEventType.START, span, [slow_processor])
        elapsed = time.monotonic() - start

        assert elapsed < 0.01, f"enqueue took {elapsed:.3f}s — should be instant"

        # Wait for the processor to start (proves it was called)
        await asyncio.wait_for(started.wait(), timeout=2.0)
        await queue.shutdown()


class TestAsyncSpanQueueOrdering:
    async def test_per_span_start_before_end(self):
        """START always completes before END for the same span, even with batching."""
        call_log: list[tuple[str, str]] = []

        async def record_start(span: Span) -> None:
            call_log.append(("start", span.id))

        async def record_end(span: Span) -> None:
            call_log.append(("end", span.id))

        proc = _make_processor(
            on_span_start=AsyncMock(side_effect=record_start),
            on_span_end=AsyncMock(side_effect=record_end),
        )
        queue = AsyncSpanQueue()

        span_a = _make_span("span-a")
        span_b = _make_span("span-b")

        queue.enqueue(SpanEventType.START, span_a, [proc])
        queue.enqueue(SpanEventType.END, span_a, [proc])
        queue.enqueue(SpanEventType.START, span_b, [proc])
        queue.enqueue(SpanEventType.END, span_b, [proc])

        await queue.shutdown()

        # All 4 events should fire
        assert len(call_log) == 4

        # Per-span invariant: START before END
        for span_id in ("span-a", "span-b"):
            start_idx = next(i for i, (ev, sid) in enumerate(call_log) if ev == "start" and sid == span_id)
            end_idx = next(i for i, (ev, sid) in enumerate(call_log) if ev == "end" and sid == span_id)
            assert start_idx < end_idx, f"START should come before END for {span_id}"

        # All STARTs before all ENDs within a batch
        start_indices = [i for i, (ev, _) in enumerate(call_log) if ev == "start"]
        end_indices = [i for i, (ev, _) in enumerate(call_log) if ev == "end"]
        assert max(start_indices) < min(end_indices), "All STARTs should complete before any END"


class TestAsyncSpanQueueErrorHandling:
    async def test_error_in_processor_does_not_stop_drain(self):
        call_count = 0

        async def failing_start(span: Span) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("simulated failure")

        proc = _make_processor(
            on_span_start=AsyncMock(side_effect=failing_start),
        )
        queue = AsyncSpanQueue()

        queue.enqueue(SpanEventType.START, _make_span(), [proc])
        queue.enqueue(SpanEventType.START, _make_span(), [proc])

        await queue.shutdown()

        assert call_count == 2, "Second event should still be processed after first fails"


class TestAsyncSpanQueueShutdown:
    async def test_shutdown_drains_remaining_items(self):
        processed: list[str] = []

        async def track(span: Span) -> None:
            processed.append(span.id)

        proc = _make_processor(on_span_start=AsyncMock(side_effect=track))
        queue = AsyncSpanQueue()

        for i in range(5):
            queue.enqueue(SpanEventType.START, _make_span(f"span-{i}"), [proc])

        await queue.shutdown()

        assert len(processed) == 5

    async def test_shutdown_timeout(self):
        async def stuck_start(span: Span) -> None:
            await asyncio.sleep(60)

        stuck_processor = _make_processor(
            on_span_start=AsyncMock(side_effect=stuck_start),
        )
        queue = AsyncSpanQueue()
        queue.enqueue(SpanEventType.START, _make_span(), [stuck_processor])

        # Give the drain loop a moment to pick up the item
        await asyncio.sleep(0.05)

        start = time.monotonic()
        await queue.shutdown(timeout=0.1)
        elapsed = time.monotonic() - start

        assert elapsed < 1.0, f"shutdown should not hang — took {elapsed:.1f}s"

    async def test_enqueue_after_shutdown_is_dropped(self):
        proc = _make_processor()
        queue = AsyncSpanQueue()
        await queue.shutdown()

        queue.enqueue(SpanEventType.START, _make_span(), [proc])

        proc.on_span_start.assert_not_called()


class TestAsyncSpanQueueBatchConcurrency:
    async def test_batch_processes_multiple_items_concurrently(self):
        """Items in the same batch should run concurrently, not serially."""
        concurrency = 0
        max_concurrency = 0
        lock = asyncio.Lock()

        async def slow_start(span: Span) -> None:
            nonlocal concurrency, max_concurrency
            async with lock:
                concurrency += 1
                max_concurrency = max(max_concurrency, concurrency)
            await asyncio.sleep(0.05)
            async with lock:
                concurrency -= 1

        proc = _make_processor(on_span_start=AsyncMock(side_effect=slow_start))
        queue = AsyncSpanQueue()

        # Enqueue 10 START events before the drain loop runs — they should
        # all land in the same batch and be processed concurrently.
        for i in range(10):
            queue.enqueue(SpanEventType.START, _make_span(f"span-{i}"), [proc])

        await queue.shutdown()

        assert max_concurrency > 1, (
            f"Expected concurrent processing, but max concurrency was {max_concurrency}"
        )

    async def test_batch_faster_than_serial(self):
        """Batched drain should be significantly faster than serial for slow processors."""
        n_items = 10
        per_item_delay = 0.05  # 50ms per processor call

        async def slow_start(span: Span) -> None:
            await asyncio.sleep(per_item_delay)

        proc = _make_processor(on_span_start=AsyncMock(side_effect=slow_start))
        queue = AsyncSpanQueue()

        for i in range(n_items):
            queue.enqueue(SpanEventType.START, _make_span(f"span-{i}"), [proc])

        start = time.monotonic()
        await queue.shutdown()
        elapsed = time.monotonic() - start

        serial_time = n_items * per_item_delay
        assert elapsed < serial_time * 0.5, (
            f"Batch drain took {elapsed:.3f}s — serial would be {serial_time:.3f}s. "
            f"Expected at least 2x speedup from concurrency."
        )


class TestAsyncSpanQueueIntegration:
    async def test_integration_with_async_trace(self):
        call_log: list[tuple[str, str]] = []

        async def record_start(span: Span) -> None:
            call_log.append(("start", span.id))

        async def record_end(span: Span) -> None:
            call_log.append(("end", span.id))

        proc = _make_processor(
            on_span_start=AsyncMock(side_effect=record_start),
            on_span_end=AsyncMock(side_effect=record_end),
        )
        queue = AsyncSpanQueue()

        # Patch get_async_tracing_processors to return our mock
        with patch(
            "agentex.lib.core.tracing.trace.get_default_span_queue",
            return_value=queue,
        ):
            from agentex.lib.core.tracing.trace import AsyncTrace

            mock_client = MagicMock()
            trace = AsyncTrace(
                processors=[proc],
                client=mock_client,
                trace_id="test-trace",
                span_queue=queue,
            )

            async with trace.span("test-operation") as span:
                output: dict[str, object] = {"result": "ok"}
                span.output = output

        await queue.shutdown()

        assert len(call_log) == 2
        assert call_log[0][0] == "start"
        assert call_log[1][0] == "end"
        # Same span ID for both events
        assert call_log[0][1] == call_log[1][1]

    async def test_end_event_drops_input(self):
        """END event should NOT carry span.input — it was already sent at START."""
        start_spans: list[Span] = []
        end_spans: list[Span] = []

        async def capture_start(span: Span) -> None:
            start_spans.append(span)

        async def capture_end(span: Span) -> None:
            end_spans.append(span)

        proc = _make_processor(
            on_span_start=AsyncMock(side_effect=capture_start),
            on_span_end=AsyncMock(side_effect=capture_end),
        )
        queue = AsyncSpanQueue()

        from agentex.lib.core.tracing.trace import AsyncTrace

        mock_client = MagicMock()
        trace = AsyncTrace(
            processors=[proc],
            client=mock_client,
            trace_id="test-trace",
            span_queue=queue,
        )

        large_input = {"system_prompt": "x" * 10_000, "messages": [{"role": "user", "content": "hi"}]}
        async with trace.span("llm-call", input=large_input) as span:
            span.output = {"response": "hello"}

        await queue.shutdown()

        assert len(start_spans) == 1
        assert len(end_spans) == 1

        # START should carry the full input
        assert start_spans[0].input is not None
        assert start_spans[0].input["system_prompt"] == "x" * 10_000

        # END should have input=None (already sent at START)
        assert end_spans[0].input is None

        # END should still carry output and end_time
        assert end_spans[0].output is not None
        assert end_spans[0].end_time is not None


class TestMemoryUsage:
    """Quantify that the fix actually reduces memory held by the tracing pipeline."""

    async def test_end_events_use_less_memory_than_start_events(self):
        """
        Simulate N concurrent single-shot requests with large system prompts.
        Collect what processors receive and measure serialized sizes.

        Before the fix, START and END events were the same size (both carried
        full input).  After the fix, END events should be dramatically smaller.
        """
        start_spans: list[Span] = []
        end_spans: list[Span] = []

        async def collect_start(span: Span) -> None:
            start_spans.append(span)

        async def collect_end(span: Span) -> None:
            end_spans.append(span)

        proc = _make_processor(
            on_span_start=AsyncMock(side_effect=collect_start),
            on_span_end=AsyncMock(side_effect=collect_end),
        )
        queue = AsyncSpanQueue()

        from agentex.lib.core.tracing.trace import AsyncTrace

        trace = AsyncTrace(
            processors=[proc],
            client=MagicMock(),
            trace_id="test-trace",
            span_queue=queue,
        )

        n_spans = 50
        prompt_size = 100_000  # 100 KB system prompt per span
        large_input = {"system_prompt": "x" * prompt_size}

        for _ in range(n_spans):
            span = await trace.start_span("llm-call", input=large_input)
            span.output = {"response": "hello"}
            await trace.end_span(span)

        await queue.shutdown()

        assert len(start_spans) == n_spans
        assert len(end_spans) == n_spans

        start_bytes = sum(len(s.model_dump_json()) for s in start_spans)
        end_bytes = sum(len(s.model_dump_json()) for s in end_spans)

        ratio = end_bytes / start_bytes
        assert ratio < 0.05, (
            f"END events used {ratio:.1%} of START event memory "
            f"(start={start_bytes:,}B, end={end_bytes:,}B). "
            f"Expected <5% because the ~{prompt_size:,}B input is dropped."
        )

    async def test_queue_payload_reduction_old_vs_new(self):
        """
        Directly compare data volume in the queue under old vs new behavior.

        Simulates a backed-up queue (drain can't keep up with request rate)
        holding N span lifecycles.  Old behavior: both START and END carry
        full input.  New behavior: END events have input=None.

        This mirrors what happens in K8s under concurrent load — items pile up
        in the queue, and each one holds a serialized copy of the system prompt.
        """
        n_spans = 30
        prompt_size = 200_000  # 200 KB system prompt

        def _queue_payload_bytes(q: AsyncSpanQueue) -> int:
            """Total serialized bytes of all spans sitting in the queue."""
            return sum(len(item.span.model_dump_json()) for item in list(q._queue._queue))

        large_input = {"system_prompt": "x" * prompt_size}

        # --- OLD behavior: both START and END carry full input ---
        old_queue = AsyncSpanQueue()
        for _ in range(n_spans):
            span = _make_span()
            span.input = large_input
            span.output = {"response": "ok"}
            old_queue._queue.put_nowait(
                _SpanQueueItem(SpanEventType.START, span.model_copy(deep=True), [])
            )
            old_queue._queue.put_nowait(
                _SpanQueueItem(SpanEventType.END, span.model_copy(deep=True), [])
            )

        # --- NEW behavior: END events drop input ---
        new_queue = AsyncSpanQueue()
        for _ in range(n_spans):
            span = _make_span()
            span.input = large_input
            span.output = {"response": "ok"}
            new_queue._queue.put_nowait(
                _SpanQueueItem(SpanEventType.START, span.model_copy(deep=True), [])
            )
            end_copy = span.model_copy(deep=True)
            end_copy.input = None
            new_queue._queue.put_nowait(
                _SpanQueueItem(SpanEventType.END, end_copy, [])
            )

        old_bytes = _queue_payload_bytes(old_queue)
        new_bytes = _queue_payload_bytes(new_queue)

        savings_pct = 1.0 - (new_bytes / old_bytes)
        assert savings_pct > 0.40, (
            f"Expected >40% queue payload reduction, got {savings_pct:.0%} "
            f"(old={old_bytes:,}B, new={new_bytes:,}B)"
        )
