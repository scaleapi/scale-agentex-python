from __future__ import annotations

import asyncio
from enum import Enum
from dataclasses import dataclass

from agentex.types.span import Span
from agentex.lib.utils.logging import make_logger
from agentex.lib.core.tracing.processors.tracing_processor_interface import (
    AsyncTracingProcessor,
)

logger = make_logger(__name__)

_DEFAULT_BATCH_SIZE = 50


class SpanEventType(str, Enum):
    START = "start"
    END = "end"


@dataclass
class _SpanQueueItem:
    event_type: SpanEventType
    span: Span
    processors: list[AsyncTracingProcessor]


class AsyncSpanQueue:
    """Background FIFO queue for async span processing.

    Span events are enqueued synchronously (non-blocking) and drained by a
    background task.  Items are processed in batches: all START events in a
    batch are flushed concurrently, then all END events, so that per-span
    start-before-end ordering is preserved while HTTP calls for independent
    spans execute in parallel.
    """

    def __init__(self, batch_size: int = _DEFAULT_BATCH_SIZE) -> None:
        self._queue: asyncio.Queue[_SpanQueueItem] = asyncio.Queue()
        self._drain_task: asyncio.Task[None] | None = None
        self._stopping = False
        self._batch_size = batch_size

    def enqueue(
        self,
        event_type: SpanEventType,
        span: Span,
        processors: list[AsyncTracingProcessor],
    ) -> None:
        if self._stopping:
            logger.warning("Span queue is shutting down, dropping %s event for span %s", event_type.value, span.id)
            return
        self._ensure_drain_running()
        self._queue.put_nowait(_SpanQueueItem(event_type=event_type, span=span, processors=processors))

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

            # Opportunistically grab more ready items (non-blocking).
            while len(batch) < self._batch_size:
                try:
                    batch.append(self._queue.get_nowait())
                except asyncio.QueueEmpty:
                    break

            try:
                # Separate START and END events.  Processing all STARTs before
                # ENDs ensures that on_span_start completes before on_span_end
                # for any span whose both events land in the same batch.
                starts = [i for i in batch if i.event_type == SpanEventType.START]
                ends = [i for i in batch if i.event_type == SpanEventType.END]

                if starts:
                    await self._process_items(starts)
                if ends:
                    await self._process_items(ends)
            finally:
                for _ in batch:
                    self._queue.task_done()
                # Release span data for GC.
                batch.clear()

    @staticmethod
    async def _process_items(items: list[_SpanQueueItem]) -> None:
        """Process a list of span events concurrently."""

        async def _handle(item: _SpanQueueItem) -> None:
            try:
                if item.event_type == SpanEventType.START:
                    coros = [p.on_span_start(item.span) for p in item.processors]
                else:
                    coros = [p.on_span_end(item.span) for p in item.processors]
                results = await asyncio.gather(*coros, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(
                            "Tracing processor error during %s for span %s",
                            item.event_type.value,
                            item.span.id,
                            exc_info=result,
                        )
            except Exception:
                logger.exception(
                    "Unexpected error in span queue for span %s", item.span.id
                )

        await asyncio.gather(*[_handle(item) for item in items])

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
            logger.warning(
                "Span queue shutdown timed out after %.1fs with %d items remaining", timeout, self._queue.qsize()
            )
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
