from __future__ import annotations

import time
import uuid
import asyncio
from typing import cast
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from agentex.types.span import Span
from agentex.lib.core.tracing.span_queue import SpanEventType, AsyncSpanQueue


def _make_span(span_id: str | None = None) -> Span:
    return Span(
        id=span_id or str(uuid.uuid4()),
        name="test-span",
        start_time=datetime.now(UTC),
        trace_id="trace-1",
    )


def _make_processor(**overrides: AsyncMock) -> AsyncMock:
    """Build a mock processor compatible with the queue's batched dispatch.

    The queue now calls on_spans_start(list) / on_spans_end(list) on each
    processor.  Mirror the behavior of AsyncTracingProcessor's default fallback
    by fanning out the list to per-span calls concurrently, so tests that
    assert on on_span_start / on_span_end continue to observe per-span calls.
    """
    proc = AsyncMock()
    proc.on_span_start = overrides.get("on_span_start", AsyncMock())
    proc.on_span_end = overrides.get("on_span_end", AsyncMock())

    async def _fanout_start(spans: list[Span]) -> None:
        await asyncio.gather(*(proc.on_span_start(s) for s in spans), return_exceptions=True)

    async def _fanout_end(spans: list[Span]) -> None:
        await asyncio.gather(*(proc.on_span_end(s) for s in spans), return_exceptions=True)

    proc.on_spans_start = AsyncMock(side_effect=_fanout_start)
    proc.on_spans_end = AsyncMock(side_effect=_fanout_end)
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

        assert max_concurrency > 1, f"Expected concurrent processing, but max concurrency was {max_concurrency}"

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


class TestProcessItemsPreconditions:
    """_process_items assumes every item in the list has the same event_type.
    Violating that precondition silently causes END events to be treated as
    STARTs (or vice versa), which is a silent data-corruption bug.  Guard it
    with an assertion."""

    async def test_mixed_event_types_raise_assertion(self):
        from agentex.lib.core.tracing.span_queue import _SpanQueueItem

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock()
        proc.on_spans_end = AsyncMock()

        mixed = [
            _SpanQueueItem(event_type=SpanEventType.START, span=_make_span("a"), processors=[proc]),
            _SpanQueueItem(event_type=SpanEventType.END, span=_make_span("b"), processors=[proc]),
        ]

        try:
            await AsyncSpanQueue()._process_items(mixed)
        except AssertionError:
            return
        else:
            raise AssertionError("Expected AssertionError for mixed event types")


class TestAsyncSpanQueueBatchedDispatch:
    """The queue should dispatch a whole drain batch to each processor via the
    batched methods (on_spans_start / on_spans_end) in one call per processor,
    so processors that support real HTTP batching can send one request instead
    of N.
    """

    async def test_batched_start_dispatch_single_call_per_drain(self):
        received: list[list[str]] = []

        async def capture_starts(spans: list[Span]) -> None:
            received.append([s.id for s in spans])

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock(side_effect=capture_starts)
        proc.on_spans_end = AsyncMock()

        queue = AsyncSpanQueue()

        # Enqueue several spans synchronously before the drain has a chance to
        # run — they should all land in a single drain batch.
        ids = [f"span-{i}" for i in range(5)]
        for i in ids:
            queue.enqueue(SpanEventType.START, _make_span(i), [proc])

        await queue.shutdown()

        # on_spans_start must have been called exactly once with all 5 spans.
        assert proc.on_spans_start.call_count == 1, f"Expected one batched call, got {proc.on_spans_start.call_count}"
        assert received == [ids]

    async def test_batched_end_dispatch_single_call_per_drain(self):
        received: list[list[str]] = []

        async def capture_ends(spans: list[Span]) -> None:
            received.append([s.id for s in spans])

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock()
        proc.on_spans_end = AsyncMock(side_effect=capture_ends)

        queue = AsyncSpanQueue()

        ids = [f"span-{i}" for i in range(5)]
        for i in ids:
            queue.enqueue(SpanEventType.END, _make_span(i), [proc])

        await queue.shutdown()

        assert proc.on_spans_end.call_count == 1
        assert received == [ids]


class TestAsyncSpanQueueLinger:
    """The drain loop should linger briefly after the first item arrives so
    that concurrently-emitted spans coalesce into one batch, instead of each
    span producing its own size-1 drain cycle.
    """

    async def test_linger_coalesces_staggered_enqueues_into_one_batch(self):
        """Spans enqueued a few ms apart should land in the SAME drain batch
        when the linger window is wider than the gap between them.
        """
        received: list[list[str]] = []

        async def capture_starts(spans: list[Span]) -> None:
            received.append([s.id for s in spans])

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock(side_effect=capture_starts)
        proc.on_spans_end = AsyncMock()

        # Linger of 100ms; we enqueue 3 items 20ms apart, well inside the window.
        queue = AsyncSpanQueue(linger_ms=100)

        for i in range(3):
            queue.enqueue(SpanEventType.START, _make_span(f"span-{i}"), [proc])
            await asyncio.sleep(0.02)

        await queue.shutdown()

        # All three should arrive in one batched call thanks to the linger.
        assert proc.on_spans_start.call_count == 1, (
            f"Expected one batch from linger-coalesced enqueues, got "
            f"{proc.on_spans_start.call_count} batches: {received}"
        )
        assert received == [["span-0", "span-1", "span-2"]]

    async def test_linger_zero_drains_immediately(self):
        """With linger_ms=0, the drain loop should NOT wait — staggered
        enqueues produce separate batches (back-compat with prior behavior).
        """
        received: list[list[str]] = []

        async def capture_starts(spans: list[Span]) -> None:
            received.append([s.id for s in spans])

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock(side_effect=capture_starts)
        proc.on_spans_end = AsyncMock()

        queue = AsyncSpanQueue(linger_ms=0)

        for i in range(3):
            queue.enqueue(SpanEventType.START, _make_span(f"span-{i}"), [proc])
            # Give the drain loop time to pick up and process each one.
            await asyncio.sleep(0.05)

        await queue.shutdown()

        # With no linger, each staggered enqueue produces its own batch.
        assert proc.on_spans_start.call_count == 3, (
            f"Expected three size-1 batches without linger, got {proc.on_spans_start.call_count}: {received}"
        )

    async def test_linger_respects_batch_size_cap(self):
        """The linger must not push batches over batch_size."""
        received: list[list[str]] = []

        async def capture_starts(spans: list[Span]) -> None:
            received.append([s.id for s in spans])

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock(side_effect=capture_starts)
        proc.on_spans_end = AsyncMock()

        # Tight batch cap, linger wide enough to coalesce but not so large
        # that the tail singleton stalls the test for hundreds of ms.
        queue = AsyncSpanQueue(batch_size=3, linger_ms=50)

        ids = [f"span-{i}" for i in range(7)]
        for i in ids:
            queue.enqueue(SpanEventType.START, _make_span(i), [proc])

        await queue.shutdown()

        # 7 spans / batch_size=3 ⇒ at least 3 batches (3, 3, 1).  None should
        # exceed the cap.
        for batch in received:
            assert len(batch) <= 3, f"Batch exceeded cap: {batch}"
        assert sum(len(b) for b in received) == 7



class _FakeHTTPError(Exception):
    """Mimics an SGP/httpx status error: carries a ``status_code`` attribute."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}")


class TestAsyncSpanQueueDropObservability:
    """Silent span loss should be counted so it is measurable, and a bounded
    queue should shed load deterministically instead of growing without limit.
    """

    async def test_full_queue_drops_are_counted(self):
        release = asyncio.Event()

        async def block_first(spans: list[Span]) -> None:
            # Block the drain on its first batch so the queue can fill behind it.
            await release.wait()

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock(side_effect=block_first)
        proc.on_spans_end = AsyncMock()

        # max_size=1, no linger, concurrency=1: the drain dispatches item-0 and
        # then blocks at the in-flight cap; item-1 fills the queue; items 2 and 3
        # are dropped.
        queue = AsyncSpanQueue(max_size=1, linger_ms=0, concurrency=1)

        queue.enqueue(SpanEventType.START, _make_span("s0"), [proc])
        await asyncio.sleep(0.02)  # let the drain pick up s0 and block
        queue.enqueue(SpanEventType.START, _make_span("s1"), [proc])
        queue.enqueue(SpanEventType.START, _make_span("s2"), [proc])
        queue.enqueue(SpanEventType.START, _make_span("s3"), [proc])

        assert queue.dropped_spans == 2, f"expected 2 dropped, got {queue.dropped_spans}"

        release.set()
        await queue.shutdown()

    async def test_no_drops_under_normal_load(self):
        proc = _make_processor()
        queue = AsyncSpanQueue()
        for i in range(5):
            queue.enqueue(SpanEventType.START, _make_span(f"s{i}"), [proc])
        await queue.shutdown()
        assert queue.dropped_spans == 0


class TestAsyncSpanQueueRetry:
    """Transient HTTP failures (429/5xx) should be re-enqueued up to a bounded
    number of attempts; auth/other errors must be dropped (and counted), never
    retried.
    """

    async def test_retryable_status_is_reenqueued_and_eventually_succeeds(self):
        attempts = 0

        async def fail_then_succeed(spans: list[Span]) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise _FakeHTTPError(503)
            # second attempt succeeds

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock(side_effect=fail_then_succeed)
        proc.on_spans_end = AsyncMock()

        queue = AsyncSpanQueue(max_retries=3, linger_ms=0)
        queue.enqueue(SpanEventType.START, _make_span("s0"), [proc])
        await queue.shutdown()

        assert attempts == 2, "503 should be retried once, then succeed"
        assert queue.dropped_spans == 0, "successful retry must not count as a drop"

    async def test_non_retryable_status_is_dropped_not_retried(self):
        attempts = 0

        async def always_401(spans: list[Span]) -> None:
            nonlocal attempts
            attempts += 1
            raise _FakeHTTPError(401)

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock(side_effect=always_401)
        proc.on_spans_end = AsyncMock()

        queue = AsyncSpanQueue(max_retries=3, linger_ms=0)
        queue.enqueue(SpanEventType.START, _make_span("s0"), [proc])
        await queue.shutdown()

        assert attempts == 1, "401 is non-retryable — must be tried exactly once"
        assert queue.dropped_spans == 1

    async def test_non_http_exception_is_not_retried(self):
        """A plain bug (no status_code) must not be retried into an infinite
        loop — preserves the original drain-continues-on-error contract."""
        attempts = 0

        async def boom(spans: list[Span]) -> None:
            nonlocal attempts
            attempts += 1
            raise RuntimeError("bug, not transient")

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock(side_effect=boom)
        proc.on_spans_end = AsyncMock()

        queue = AsyncSpanQueue(max_retries=3, linger_ms=0)
        queue.enqueue(SpanEventType.START, _make_span("s0"), [proc])
        await queue.shutdown()

        assert attempts == 1
        assert queue.dropped_spans == 1

    async def test_retryable_exhausts_attempts_then_drops(self):
        attempts = 0

        async def always_503(spans: list[Span]) -> None:
            nonlocal attempts
            attempts += 1
            raise _FakeHTTPError(503)

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock(side_effect=always_503)
        proc.on_spans_end = AsyncMock()

        queue = AsyncSpanQueue(max_retries=3, linger_ms=0)
        queue.enqueue(SpanEventType.START, _make_span("s0"), [proc])
        await queue.shutdown()

        assert attempts == 3, "should try up to max_retries times"
        assert queue.dropped_spans == 1


class TestAsyncSpanQueueConcurrency:
    """Span export should issue multiple batch requests concurrently (bounded),
    so per-pod egress isn't capped at one in-flight request — while still
    guaranteeing a span's START send completes before its END send.
    """

    async def test_batches_dispatched_concurrently_up_to_bound(self):
        current = 0
        max_seen = 0
        lock = asyncio.Lock()

        async def slow_start(spans: list[Span]) -> None:
            nonlocal current, max_seen
            async with lock:
                current += 1
                max_seen = max(max_seen, current)
            await asyncio.sleep(0.05)
            async with lock:
                current -= 1

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock(side_effect=slow_start)
        proc.on_spans_end = AsyncMock()

        # batch_size=1 → each span is its own batch/send; concurrency=4 caps
        # simultaneous in-flight sends.
        queue = AsyncSpanQueue(batch_size=1, linger_ms=0, concurrency=4)
        for i in range(8):
            queue.enqueue(SpanEventType.START, _make_span(f"s{i}"), [proc])

        await queue.shutdown()

        assert proc.on_spans_start.call_count == 8
        assert 2 <= max_seen <= 4, f"expected bounded concurrency (2..4), saw {max_seen}"

    async def test_concurrency_one_serializes(self):
        current = 0
        max_seen = 0
        lock = asyncio.Lock()

        async def slow_start(spans: list[Span]) -> None:
            nonlocal current, max_seen
            async with lock:
                current += 1
                max_seen = max(max_seen, current)
            await asyncio.sleep(0.03)
            async with lock:
                current -= 1

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock(side_effect=slow_start)
        proc.on_spans_end = AsyncMock()

        queue = AsyncSpanQueue(batch_size=1, linger_ms=0, concurrency=1)
        for i in range(4):
            queue.enqueue(SpanEventType.START, _make_span(f"s{i}"), [proc])

        await queue.shutdown()

        assert max_seen == 1, f"concurrency=1 must serialize sends, saw {max_seen}"

    async def test_concurrent_is_faster_than_serial(self):
        async def slow_start(spans: list[Span]) -> None:
            await asyncio.sleep(0.05)

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock(side_effect=slow_start)
        proc.on_spans_end = AsyncMock()

        queue = AsyncSpanQueue(batch_size=1, linger_ms=0, concurrency=8)
        for i in range(8):
            queue.enqueue(SpanEventType.START, _make_span(f"s{i}"), [proc])

        start = time.monotonic()
        await queue.shutdown()
        elapsed = time.monotonic() - start

        serial = 8 * 0.05
        assert elapsed < serial * 0.5, f"concurrent drain took {elapsed:.3f}s; serial would be {serial:.3f}s"

    async def test_end_waits_for_start_of_same_span(self):
        """The per-span ordering invariant: a span's END upsert must not be sent
        until its START upsert has completed, even with concurrency enabled."""
        log: list[tuple[str, str]] = []

        async def on_start(spans: list[Span]) -> None:
            log.append(("start_enter", spans[0].id))
            await asyncio.sleep(0.05)
            log.append(("start_exit", spans[0].id))

        async def on_end(spans: list[Span]) -> None:
            log.append(("end_enter", spans[0].id))
            await asyncio.sleep(0.01)
            log.append(("end_exit", spans[0].id))

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock(side_effect=on_start)
        proc.on_spans_end = AsyncMock(side_effect=on_end)

        queue = AsyncSpanQueue(batch_size=1, linger_ms=0, concurrency=4)
        queue.enqueue(SpanEventType.START, _make_span("A"), [proc])
        await asyncio.sleep(0.01)  # let the START send begin (and block on sleep)
        queue.enqueue(SpanEventType.END, _make_span("A"), [proc])

        await queue.shutdown()

        # END must not enter until START has exited for the same span.
        start_exit = log.index(("start_exit", "A"))
        end_enter = log.index(("end_enter", "A"))
        assert start_exit < end_enter, f"END began before START completed: {log}"


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

    async def test_end_event_preserves_modified_input(self):
        """END event should carry span.input so modifications after start are preserved."""
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

        initial_input: dict[str, object] = {"messages": [{"role": "user", "content": "hello"}]}
        async with trace.span("llm-call", input=initial_input) as span:
            # Simulate modifying input after start (e.g. chatbot appending messages)
            messages = cast(list[dict[str, str]], cast(dict[str, object], span.input)["messages"])
            messages.append({"role": "assistant", "content": "hi there"})
            messages.append({"role": "user", "content": "how are you?"})
            span.output = cast(dict[str, object], {"response": "I'm good!"})

        await queue.shutdown()

        assert len(start_spans) == 1
        assert len(end_spans) == 1

        # START should carry the original input (serialized at start time)
        assert start_spans[0].input is not None
        assert len(cast(dict[str, list[object]], start_spans[0].input)["messages"]) == 1  # only the original message

        # END should carry the modified input (re-serialized at end time)
        assert end_spans[0].input is not None
        assert len(cast(dict[str, list[object]], end_spans[0].input)["messages"]) == 3  # all three messages

        # END should still carry output and end_time
        assert end_spans[0].output is not None
        assert end_spans[0].end_time is not None


class TestAsyncSpanQueueMetrics:
    async def test_batch_coalesced_records_depth_including_batch(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_METRICS", "1")
        import agentex.lib.core.observability.tracing_metrics_recording as recording

        recording._metrics_enabled = None
        proc = _make_processor()
        queue = AsyncSpanQueue(linger_ms=0)
        recorded_depths: list[int] = []

        def capture_coalesced(*, queue_depth: int, batch_items: object) -> None:
            recorded_depths.append(queue_depth)

        with patch.object(recording, "record_batch_coalesced", side_effect=capture_coalesced):
            for _ in range(3):
                queue.enqueue(SpanEventType.START, _make_span(), [proc])
            await asyncio.sleep(0.05)
            await queue.shutdown()

        assert recorded_depths, "expected at least one coalesced batch"
        assert recorded_depths[0] >= 3, (
            f"queue_depth should include batch items removed from queue, got {recorded_depths[0]}"
        )

    async def test_enqueue_records_enqueued_metric(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_METRICS", "1")
        import agentex.lib.core.observability.tracing_metrics_recording as recording

        recording._metrics_enabled = None
        recording._tracing = None
        mock_metrics = MagicMock()
        proc = _make_processor()
        queue = AsyncSpanQueue()

        with patch(
            "agentex.lib.core.observability.tracing_metrics.get_tracing_metrics",
            return_value=mock_metrics,
        ):
            queue.enqueue(SpanEventType.START, _make_span(), [proc])
            await asyncio.sleep(0.05)
            await queue.shutdown()

        mock_metrics.span_events_enqueued.add.assert_any_call(1, {"event_type": "start"})

    async def test_enqueue_during_shutdown_records_dropped_metric(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_METRICS", "1")
        import agentex.lib.core.observability.tracing_metrics_recording as recording

        recording._metrics_enabled = None
        recording._tracing = None
        mock_metrics = MagicMock()
        proc = _make_processor()
        queue = AsyncSpanQueue(linger_ms=0)

        with patch(
            "agentex.lib.core.observability.tracing_metrics.get_tracing_metrics",
            return_value=mock_metrics,
        ):
            queue.enqueue(SpanEventType.START, _make_span(), [proc])
            await asyncio.sleep(0.05)
            queue._stopping = True
            queue.enqueue(SpanEventType.END, _make_span(), [proc])
            await queue.shutdown()

        mock_metrics.span_events_dropped.add.assert_any_call(1, {"reason": "shutdown"})

    async def test_processor_failure_records_export_failure(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_METRICS", "1")
        import agentex.lib.core.observability.tracing_metrics_recording as recording

        recording._metrics_enabled = None
        recording._tracing = None
        mock_metrics = MagicMock()

        class ExportError(Exception):
            pass

        proc = AsyncMock()
        proc.on_spans_start = AsyncMock(side_effect=ExportError("Error code: 401 - denied"))
        proc.on_spans_end = AsyncMock()
        queue = AsyncSpanQueue()

        with patch(
            "agentex.lib.core.observability.tracing_metrics.get_tracing_metrics",
            return_value=mock_metrics,
        ):
            queue.enqueue(SpanEventType.START, _make_span(), [proc])
            await asyncio.sleep(0.05)
            await queue.shutdown()

        mock_metrics.export_batch_failures.add.assert_called_once()
        mock_metrics.export_span_failures.add.assert_called_once()

    async def test_enqueue_overhead_with_metrics_disabled(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_METRICS", "0")
        import agentex.lib.core.observability.tracing_metrics_recording as recording

        recording._metrics_enabled = None
        recording._tracing = None
        proc = _make_processor()
        queue = AsyncSpanQueue()

        with patch(
            "agentex.lib.core.observability.tracing_metrics.get_tracing_metrics"
        ) as mock_get:
            start = time.monotonic()
            for _ in range(200):
                queue.enqueue(SpanEventType.START, _make_span(), [proc])
            elapsed = time.monotonic() - start
            await queue.shutdown()

        assert elapsed < 0.05, f"disabled metrics enqueue too slow: {elapsed:.3f}s"
        mock_get.assert_not_called()
