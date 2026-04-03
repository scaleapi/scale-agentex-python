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

    Span events are enqueued synchronously (non-blocking) and processed
    sequentially by a background drain task. This keeps tracing HTTP calls
    off the critical request path while preserving start-before-end ordering.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[_SpanQueueItem] = asyncio.Queue()
        self._drain_task: asyncio.Task[None] | None = None
        self._stopping = False

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

    async def _drain_loop(self) -> None:
        while True:
            item = await self._queue.get()
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
                logger.exception("Unexpected error in span queue drain loop for span %s", item.span.id)
            finally:
                self._queue.task_done()

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
