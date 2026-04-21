import asyncio
from abc import ABC, abstractmethod

from agentex.types.span import Span
from agentex.lib.types.tracing import TracingProcessorConfig


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
        """
        await asyncio.gather(*(self.on_span_start(s) for s in spans), return_exceptions=False)

    async def on_spans_end(self, spans: list[Span]) -> None:
        """Batched variant of on_span_end.  See on_spans_start for details."""
        await asyncio.gather(*(self.on_span_end(s) for s in spans), return_exceptions=False)

    @abstractmethod
    async def shutdown(self) -> None:
        pass
