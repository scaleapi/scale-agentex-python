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

    @abstractmethod
    async def shutdown(self) -> None:
        pass
