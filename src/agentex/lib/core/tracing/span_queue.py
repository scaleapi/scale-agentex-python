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


def _read_linger_ms_env() -> int:
    """Read AGENTEX_SPAN_QUEUE_LINGER_MS from the environment, falling back to
    _DEFAULT_LINGER_MS when unset or unparseable.  Negative values are clamped
    to 0 (i.e. "drain immediately, no linger")."""
    raw = os.environ.get("AGENTEX_SPAN_QUEUE_LINGER_MS")
    if raw is None:
        return _DEFAULT_LINGER_MS
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning(
            "Ignoring invalid AGENTEX_SPAN_QUEUE_LINGER_MS=%r; using default %d ms",
            raw,
            _DEFAULT_LINGER_MS,
        )
        return _DEFAULT_LINGER_MS


class SpanEventType(str, Enum):
    START = "start"
    END = "end"


@dataclass
class _SpanQueueItem:
    event_type: SpanEventType
    span: Span
    processors: list[AsyncTracingProcessor]
    enqueued_at: float | None = None


class AsyncSpanQueue:
    """Background FIFO queue for async span processing.

    Span events are enqueued synchronously (non-blocking) and drained by a
    background task.  Items are processed in batches: all START events in a
    batch are flushed concurrently, then all END events, so that per-span
    start-before-end ordering is preserved while HTTP calls for independent
    spans execute in parallel.

    Once the drain loop picks up the first item, it lingers up to
    ``linger_ms`` waiting for more items to coalesce into the same batch.
    Without the linger the drain almost always returned size-1 batches under
    real agent workloads, because spans typically arrive a few ms apart.
    """

    def __init__(
        self,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        linger_ms: int | None = None,
    ) -> None:
        self._queue: asyncio.Queue[_SpanQueueItem] = asyncio.Queue()
        self._drain_task: asyncio.Task[None] | None = None
        self._stopping = False
        self._batch_size = batch_size
        self._linger_ms = _read_linger_ms_env() if linger_ms is None else max(0, linger_ms)

    def enqueue(
        self,
        event_type: SpanEventType,
        span: Span,
        processors: list[AsyncTracingProcessor],
    ) -> None:
        if self._stopping:
            logger.warning("Span queue is shutting down, dropping %s event for span %s", event_type.value, span.id)
            _metrics.record_span_dropped("shutdown")
            return
        self._ensure_drain_running()
        self._queue.put_nowait(
            _SpanQueueItem(
                event_type=event_type,
                span=span,
                processors=processors,
                enqueued_at=_metrics.monotonic_if_enabled(),
            )
        )
        _metrics.record_span_enqueued(event_type.value)

    def _ensure_drain_running(self) -> None:
        if self._drain_task is None or self._drain_task.done():
            self._drain_task = asyncio.create_task(self._drain_loop())

    # ------------------------------------------------------------------
    # Drain loop
    # ------------------------------------------------------------------

    async def _drain_loop(self) -> None:
        while True:
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
                        batch.append(
                            await asyncio.wait_for(self._queue.get(), timeout=remaining)
                        )
                    except asyncio.TimeoutError:
                        break
            else:
                # No linger — drain whatever is already queued and stop.
                while len(batch) < self._batch_size:
                    try:
                        batch.append(self._queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

            try:
                _metrics.record_batch_coalesced(
                    queue_depth=self._queue.qsize() + len(batch),
                    batch_items=batch,
                )

                # Separate START and END events.  Processing all STARTs before
                # ENDs ensures that on_span_start completes before on_span_end
                # for any span whose both events land in the same batch.
                starts = [i for i in batch if i.event_type == SpanEventType.START]
                ends = [i for i in batch if i.event_type == SpanEventType.END]

                if starts:
                    phase_start = time.perf_counter()
                    await self._process_items(starts)
                    _metrics.record_batch_phase(
                        phase="start",
                        size=len(starts),
                        duration_ms=(time.perf_counter() - phase_start) * 1000.0,
                    )
                if ends:
                    phase_start = time.perf_counter()
                    await self._process_items(ends)
                    _metrics.record_batch_phase(
                        phase="end",
                        size=len(ends),
                        duration_ms=(time.perf_counter() - phase_start) * 1000.0,
                    )
            finally:
                for _ in batch:
                    self._queue.task_done()
                # Release span data for GC.
                batch.clear()

    @staticmethod
    async def _process_items(items: list[_SpanQueueItem]) -> None:
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
        by_processor: dict[AsyncTracingProcessor, list[Span]] = {}
        for item in items:
            for p in item.processors:
                by_processor.setdefault(p, []).append(item.span)

        async def _handle(p: AsyncTracingProcessor, spans: list[Span]) -> None:
            try:
                if event_type == SpanEventType.START:
                    await p.on_spans_start(spans)
                else:
                    await p.on_spans_end(spans)
            except Exception as exc:
                logger.exception(
                    "Tracing processor %s failed handling %d spans during %s",
                    type(p).__name__,
                    len(spans),
                    event_type.value,
                )
                _metrics.record_export_failure(
                    processor=p,
                    event_type=event_type.value,
                    span_count=len(spans),
                    exc=exc,
                )

        await asyncio.gather(*[_handle(p, spans) for p, spans in by_processor.items()])

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def shutdown(self, timeout: float = 30.0) -> None:
        self._stopping = True
        if self._queue.empty() and (self._drain_task is None or self._drain_task.done()):
            return
        try:
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
        except asyncio.TimeoutError:
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
