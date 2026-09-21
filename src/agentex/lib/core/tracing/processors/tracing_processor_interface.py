from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

from agentex.types.span import Span
from agentex.lib.types.tracing import TracingProcessorConfig
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class SyncTracingProcessor(ABC):
    @abstractmethod
    def __init__(self, config: TracingProcessorConfig):
        pass

    @abstractmethod
    def on_span_start(self, span: Span) -> None:
        pass

    @abstractmethod
    def on_span_end(self, span: Span) -> None:
        pass

    @abstractmethod
    def shutdown(self) -> None:
        pass


class AsyncTracingProcessor(ABC):
    @abstractmethod
    def __init__(self, config: TracingProcessorConfig):
        pass

    @abstractmethod
    async def on_span_start(self, span: Span) -> None:
        pass

    @abstractmethod
    async def on_span_end(self, span: Span) -> None:
        pass

    async def on_spans_start(self, spans: list[Span]) -> None:
        """Batched variant of on_span_start.

        Default fallback fans out to the single-span method in parallel so
        existing processors keep working unchanged.  Processors that support
        real batching (e.g. sending all spans in one HTTP call) should
        override this to avoid the per-span round trip.

        Per-span exceptions are captured and logged individually so that one
        failing span does not prevent the others from being processed.
        """
        results = await asyncio.gather(
            *(self.on_span_start(s) for s in spans), return_exceptions=True
        )
        for span, result in zip(spans, results):
            if isinstance(result, Exception):
                logger.error(
                    "Tracing processor %s failed on_span_start for span %s",
                    type(self).__name__,
                    span.id,
                    exc_info=result,
                )

    async def on_spans_end(self, spans: list[Span]) -> None:
        """Batched variant of on_span_end.  See on_spans_start for details."""
        results = await asyncio.gather(
            *(self.on_span_end(s) for s in spans), return_exceptions=True
        )
        for span, result in zip(spans, results):
            if isinstance(result, Exception):
                logger.error(
                    "Tracing processor %s failed on_span_end for span %s",
                    type(self).__name__,
                    span.id,
                    exc_info=result,
                )

    @abstractmethod
    async def shutdown(self) -> None:
        pass
