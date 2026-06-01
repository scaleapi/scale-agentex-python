from __future__ import annotations

import os
import time
import asyncio
from enum import Enum
from dataclasses import dataclass

from agentex.types.span import Span
from agentex.lib.utils.logging import make_logger
from agentex.lib.core.observability import tracing_metrics_recording as _metrics
from agentex.lib.core.tracing.processors.tracing_processor_interface import (
    AsyncTracingProcessor,
)

logger = make_logger(__name__)

_DEFAULT_BATCH_SIZE = 50
_DEFAULT_LINGER_MS = 100
# 0 == unbounded (preserves prior behavior).  A bound makes backpressure
# visible (dropped spans are counted) and caps worst-case memory.
_DEFAULT_MAX_SIZE = 0
# Total attempts per batch for a *transient* failure (1 == no retry).
_DEFAULT_MAX_RETRIES = 1
# Max number of batch-export HTTP requests in flight at once.  The export
# backend (EGP) processes each upsert_batch in ~150ms but serves many requests
# concurrently; issuing one batch at a time caps per-pod egress at ~1/latency.
# Sending several concurrently lets a pod keep up with span production under
# load.  ``1`` restores the old strictly-serial behavior.
_DEFAULT_CONCURRENCY = 3
# HTTP statuses worth retrying at the queue level.  These are explicit
# backpressure / transient signals; everything else (esp. 401/403/4xx auth and
# validation errors) is a permanent failure that re-enqueuing cannot fix.  Note
# the underlying SGP client already retries these internally, so queue-level
# retry only helps when its budget is exhausted by a longer blip.
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def _read_int_env(name: str, default: int, *, minimum: int = 0) -> int:
    """Read a non-negative int from the environment, clamping to ``minimum``
    and falling back to ``default`` when unset or unparseable."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        logger.warning("Ignoring invalid %s=%r; using default %d", name, raw, default)
        return default


def _read_linger_ms_env() -> int:
    """Read AGENTEX_SPAN_QUEUE_LINGER_MS from the environment, falling back to
    _DEFAULT_LINGER_MS when unset or unparseable.  Negative values are clamped
    to 0 (i.e. "drain immediately, no linger")."""
    return _read_int_env("AGENTEX_SPAN_QUEUE_LINGER_MS", _DEFAULT_LINGER_MS)


def _is_retryable_exc(exc: BaseException) -> bool:
    """A failure is retryable only when it carries an HTTP ``status_code`` in
    the retryable set.  Connection/timeout errors (no status_code) have already
    been retried by the SGP client, and bare exceptions (programming bugs) must
    never be retried — re-enqueuing them would spin forever."""
    status_code = getattr(exc, "status_code", None)
    return isinstance(status_code, int) and status_code in _RETRYABLE_STATUS_CODES


class SpanEventType(str, Enum):
    START = "start"
    END = "end"


@dataclass
class _SpanQueueItem:
    event_type: SpanEventType
    span: Span
    processors: list[AsyncTracingProcessor]
    enqueued_at: float | None = None
    # Number of times this item has already been dispatched.  Used to bound
    # re-enqueue on transient failures.
    attempts: int = 0


class AsyncSpanQueue:
    """Background FIFO queue for async span processing.

    Span events are enqueued synchronously (non-blocking) and drained by a
    background task.  The drain coalesces ready events into batches and
    *dispatches* each batch's export as its own task, so up to ``concurrency``
    batch requests can be in flight at once.  This matters because each
    ``upsert_batch`` HTTP call takes tens-to-hundreds of ms server-side; issuing
    them one at a time caps a pod's egress at ~1/latency and lets a backlog
    build under load.

    Ordering guarantee: a span's START export always completes before its END
    export is issued.  END batches wait on the START batches that were in flight
    when they were formed; because a span's START is always enqueued before its
    END, that span's START send is either still in flight (and waited on) or
    already finished.  Independent spans export fully concurrently.

    Once the drain loop picks up the first item, it lingers up to ``linger_ms``
    waiting for more items to coalesce into the same batch.  Without the linger
    the drain almost always returned size-1 batches under real agent workloads,
    because spans typically arrive a few ms apart.

    Reliability:
    - ``max_size`` bounds the queue.  When full, new events are dropped and
      counted (see ``dropped_spans``) rather than growing memory without limit.
      ``0`` keeps the queue unbounded.
    - A batch that fails with a *transient* HTTP status (429/5xx) is
      re-enqueued up to ``max_retries`` total attempts.  Permanent failures
      (auth/validation/bugs) are dropped and counted immediately.
    """

    def __init__(
        self,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        linger_ms: int | None = None,
        max_size: int | None = None,
        max_retries: int | None = None,
        concurrency: int | None = None,
    ) -> None:
        resolved_max_size = (
            _read_int_env("AGENTEX_SPAN_QUEUE_MAX_SIZE", _DEFAULT_MAX_SIZE) if max_size is None else max(0, max_size)
        )
        self._queue: asyncio.Queue[_SpanQueueItem] = asyncio.Queue(maxsize=resolved_max_size)
        self._drain_task: asyncio.Task[None] | None = None
        self._stopping = False
        self._batch_size = batch_size
        self._linger_ms = _read_linger_ms_env() if linger_ms is None else max(0, linger_ms)
        self._max_retries = (
            _read_int_env("AGENTEX_SPAN_QUEUE_MAX_RETRIES", _DEFAULT_MAX_RETRIES, minimum=1)
            if max_retries is None
            else max(1, max_retries)
        )
        self._concurrency = (
            _read_int_env("AGENTEX_SPAN_QUEUE_CONCURRENCY", _DEFAULT_CONCURRENCY, minimum=1)
            if concurrency is None
            else max(1, concurrency)
        )
        # Bounds concurrent export HTTP requests.
        self._send_sema = asyncio.Semaphore(self._concurrency)
        # Outstanding dispatched send tasks, and the subset that are START
        # sends (END sends wait on these to preserve per-span ordering).
        self._inflight: set[asyncio.Task[None]] = set()
        self._inflight_starts: set[asyncio.Task[None]] = set()
        # Total spans dropped for any reason (full queue, shutdown, permanent
        # failure, exhausted retries).  Surfaced for metrics/observability so
        # span loss stops being silent.
        self._dropped_spans = 0

    @property
    def dropped_spans(self) -> int:
        """Cumulative count of spans dropped (never delivered)."""
        return self._dropped_spans

    @property
    def depth(self) -> int:
        """Current number of items waiting in the queue."""
        return self._queue.qsize()

    def _record_drop(self, count: int, reason: str) -> None:
        if count <= 0:
            return
        self._dropped_spans += count
        if "shutdown" in reason:
            for _ in range(count):
                _metrics.record_span_dropped("shutdown")
        elif "queue full" in reason:
            for _ in range(count):
                _metrics.record_span_dropped("queue_full")
        # Warn on the first drop and then sparsely, so a drop storm is visible
        # without flooding the log.
        if self._dropped_spans == count or self._dropped_spans % 100 < count:
            logger.warning(
                "Span queue dropped %d span(s) (%s); %d dropped in total",
                count,
                reason,
                self._dropped_spans,
            )

    def enqueue(
        self,
        event_type: SpanEventType,
        span: Span,
        processors: list[AsyncTracingProcessor],
    ) -> None:
        if self._stopping:
            self._record_drop(1, "queue shutting down")
            return
        self._ensure_drain_running()
        try:
            self._queue.put_nowait(
                _SpanQueueItem(
                    event_type=event_type,
                    span=span,
                    processors=processors,
                    enqueued_at=_metrics.monotonic_if_enabled(),
                )
            )
            _metrics.record_span_enqueued(event_type.value)
        except asyncio.QueueFull:
            self._record_drop(1, "queue full")

    def _ensure_drain_running(self) -> None:
        if self._drain_task is None or self._drain_task.done():
            self._drain_task = asyncio.create_task(self._drain_loop())

    # ------------------------------------------------------------------
    # Drain loop
    # ------------------------------------------------------------------

    async def _drain_loop(self) -> None:
        while True:
            # Backpressure: cap the number of in-flight send tasks so the drain
            # does not run unboundedly ahead of the exporters.
            while len(self._inflight) >= self._concurrency:
                await asyncio.wait(set(self._inflight), return_when=asyncio.FIRST_COMPLETED)

            # Block until at least one item is available.
            first = await self._queue.get()
            batch: list[_SpanQueueItem] = [first]

            # Linger briefly so spans emitted within the window coalesce into
            # one batch.  Stop early when the batch fills, when the linger
            # window elapses, or as soon as the queue is briefly empty *after*
            # the deadline.
            if self._linger_ms > 0 and not self._stopping:
                loop = asyncio.get_running_loop()
                deadline = loop.time() + (self._linger_ms / 1000.0)
                while len(batch) < self._batch_size:
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        break
                    try:
                        batch.append(await asyncio.wait_for(self._queue.get(), timeout=remaining))
                    except asyncio.TimeoutError:
                        break
            else:
                # No linger — drain whatever is already queued and stop.
                while len(batch) < self._batch_size:
                    try:
                        batch.append(self._queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

            _metrics.record_batch_coalesced(
                queue_depth=self._queue.qsize() + len(batch),
                batch_items=batch,
            )

            # Separate START and END events and dispatch each as its own send
            # task.  Dispatching STARTs first (so they are registered before the
            # END snapshot) guarantees an END never outruns a START of the same
            # span whose events land in this batch.
            starts = [i for i in batch if i.event_type == SpanEventType.START]
            ends = [i for i in batch if i.event_type == SpanEventType.END]
            if starts:
                self._dispatch(starts, SpanEventType.START)
            if ends:
                # Re-check backpressure before the second dispatch so a batch
                # carrying both event types can't push _inflight past the cap.
                while len(self._inflight) >= self._concurrency:
                    await asyncio.wait(set(self._inflight), return_when=asyncio.FIRST_COMPLETED)
                self._dispatch(ends, SpanEventType.END)

    def _dispatch(self, items: list[_SpanQueueItem], event_type: SpanEventType) -> None:
        """Spawn a background task to export ``items``.

        END sends snapshot the currently in-flight START tasks and wait for them
        before issuing, preserving the per-span START-before-END invariant.
        """
        barrier = tuple(self._inflight_starts) if event_type == SpanEventType.END else ()
        task = asyncio.create_task(self._run_send(items, barrier))
        self._inflight.add(task)
        task.add_done_callback(self._inflight.discard)
        if event_type == SpanEventType.START:
            self._inflight_starts.add(task)
            task.add_done_callback(self._inflight_starts.discard)

    async def _run_send(self, items: list[_SpanQueueItem], barrier: tuple[asyncio.Task[None], ...]) -> None:
        try:
            if barrier:
                # Wait for the START sends this END batch depends on.  Their
                # exceptions are irrelevant here — we only need them finished.
                await asyncio.gather(*barrier, return_exceptions=True)
            phase_start = time.perf_counter()
            await self._process_items(items)
            if items:
                _metrics.record_batch_phase(
                    phase=items[0].event_type.value,
                    size=len(items),
                    duration_ms=(time.perf_counter() - phase_start) * 1000.0,
                )
        finally:
            # Mark every item done so shutdown's queue.join() can complete only
            # once all sends (and their retries) have finished.
            for _ in items:
                self._queue.task_done()

    async def _process_items(self, items: list[_SpanQueueItem]) -> None:
        """Dispatch a batch of same-event-type items to each processor in one call.

        Groups spans by processor so each processor sees its full slice of the
        drain batch at once.  Processors that override the batched methods can
        then send a single HTTP request per drain cycle instead of N.
        """
        if not items:
            return

        event_type = items[0].event_type
        assert all(i.event_type == event_type for i in items), (
            "_process_items requires all items to share the same event_type; "
            "callers must split START and END batches before dispatching."
        )
        by_processor: dict[AsyncTracingProcessor, list[_SpanQueueItem]] = {}
        for item in items:
            for p in item.processors:
                by_processor.setdefault(p, []).append(item)

        await asyncio.gather(*[self._handle(p, batch, event_type) for p, batch in by_processor.items()])

    async def _handle(
        self,
        p: AsyncTracingProcessor,
        items: list[_SpanQueueItem],
        event_type: SpanEventType,
    ) -> None:
        spans = [item.span for item in items]
        try:
            # Hold a concurrency slot only for the duration of the HTTP call.
            async with self._send_sema:
                if event_type == SpanEventType.START:
                    await p.on_spans_start(spans)
                else:
                    await p.on_spans_end(spans)
        except Exception as exc:
            self._handle_failure(p, items, event_type, exc)

    def _handle_failure(
        self,
        p: AsyncTracingProcessor,
        items: list[_SpanQueueItem],
        event_type: SpanEventType,
        exc: Exception,
    ) -> None:
        # Re-enqueue transient failures, drop everything else.  Re-enqueue is
        # bounded by max_retries, so even during shutdown the queue's join()
        # still terminates after a finite number of passes.
        if _is_retryable_exc(exc):
            retriable = [item for item in items if item.attempts + 1 < self._max_retries]
            exhausted = len(items) - len(retriable)
            if exhausted:
                self._record_drop(exhausted, f"{type(p).__name__} retries exhausted during {event_type.value}")
                _metrics.record_export_failure(
                    processor=p,
                    event_type=event_type.value,
                    span_count=exhausted,
                    exc=exc,
                )
            for item in retriable:
                self._reenqueue(item, p)
            if retriable:
                logger.warning(
                    "Tracing processor %s failed handling %d spans during %s (%s); re-enqueued %d for retry",
                    type(p).__name__,
                    len(items),
                    event_type.value,
                    type(exc).__name__,
                    len(retriable),
                )
            return

        self._record_drop(len(items), f"{type(p).__name__} permanent failure during {event_type.value}")
        logger.exception(
            "Tracing processor %s failed handling %d spans during %s",
            type(p).__name__,
            len(items),
            event_type.value,
        )
        _metrics.record_export_failure(
            processor=p,
            event_type=event_type.value,
            span_count=len(items),
            exc=exc,
        )

    def _reenqueue(self, item: _SpanQueueItem, p: AsyncTracingProcessor) -> None:
        """Put a single failed item back on the queue, scoped to the processor
        that failed, with an incremented attempt count.

        NOTE: a re-enqueued START goes to the *back* of the queue.  If an END
        for the same span is dispatched concurrently before this START is picked
        up again, the END's barrier snapshot won't contain it, breaking the
        START-before-END guarantee for that span.  This is benign at the default
        ``max_retries=1`` (retries disabled) but must be addressed before
        enabling retries by default."""
        try:
            self._queue.put_nowait(
                _SpanQueueItem(
                    event_type=item.event_type,
                    span=item.span,
                    processors=[p],
                    enqueued_at=item.enqueued_at,
                    attempts=item.attempts + 1,
                )
            )
        except asyncio.QueueFull:
            self._record_drop(1, "queue full on retry")

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def shutdown(self, timeout: float = 30.0) -> None:
        self._stopping = True
        drain_idle = self._drain_task is None or self._drain_task.done()
        if self._queue.empty() and drain_idle and not self._inflight:
            return

        timed_out = False
        try:
            # join() returns once every enqueued (and re-enqueued) item has been
            # marked done by its send task.
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
        except asyncio.TimeoutError:
            timed_out = True
            remaining = self._queue.qsize()
            logger.warning(
                "Span queue shutdown timed out after %.1fs with %d items remaining", timeout, remaining
            )
            _metrics.record_shutdown_timeout(remaining_items=remaining)

        if self._drain_task is not None and not self._drain_task.done():
            self._drain_task.cancel()
            try:
                await self._drain_task
            except asyncio.CancelledError:
                pass

        # Clean up any in-flight send tasks.  On a clean shutdown these are
        # already finishing; on timeout, cancel the stragglers so we don't hang.
        inflight = list(self._inflight)
        if inflight:
            if timed_out:
                for task in inflight:
                    task.cancel()
            await asyncio.gather(*inflight, return_exceptions=True)


_default_span_queue: AsyncSpanQueue | None = None


def get_default_span_queue() -> AsyncSpanQueue:
    global _default_span_queue
    if _default_span_queue is None:
        _default_span_queue = AsyncSpanQueue()
    return _default_span_queue


async def shutdown_default_span_queue(timeout: float = 30.0) -> None:
    global _default_span_queue
    if _default_span_queue is not None:
        await _default_span_queue.shutdown(timeout=timeout)
        _default_span_queue = None
