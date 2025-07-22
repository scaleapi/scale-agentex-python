import asyncio
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from typing import Any, AsyncGenerator
import uuid

from pydantic import BaseModel

from agentex import Agentex, AsyncAgentex
from agentex.lib.core.tracing.processors.tracing_processor_interface import (
    AsyncTracingProcessor,
    SyncTracingProcessor,
)
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import recursive_model_dump
from agentex.types.span import Span

logger = make_logger(__name__)


class Trace:
    """
    Trace is a wrapper around the Agentex API for tracing.
    It provides a context manager for spans and a way to start and end spans.
    It also provides a way to get spans by ID and list all spans in a trace.
    """

    def __init__(
        self,
        processors: list[SyncTracingProcessor],
        client: Agentex,
        trace_id: str | None = None,
    ):
        """
        Initialize a new trace with the specified trace ID.

        Args:
            trace_id: Required trace ID to use for this trace.
            processors: Optional list of tracing processors to use for this trace.
        """
        self.processors = processors
        self.client = client
        self.trace_id = trace_id

    def start_span(
        self,
        name: str,
        parent_id: str | None = None,
        input: dict[str, Any] | list[dict[str, Any]] | BaseModel | None = None,
        data: dict[str, Any] | list[dict[str, Any]] | BaseModel | None = None,
    ) -> Span:
        """
        Start a new span and register it with the API.

        Args:
            name: Name of the span.
            parent_id: Optional parent span ID.
            input: Optional input data for the span.
            data: Optional additional data for the span.

        Returns:
            The newly created span.
        """

        if not self.trace_id:
            raise ValueError("Trace ID is required to start a span")

        # Create a span using the client's spans resource
        start_time = datetime.now(UTC)

        serialized_input = recursive_model_dump(input) if input else None
        serialized_data = recursive_model_dump(data) if data else None
        id = str(uuid.uuid4())

        span = Span(
            id=id,
            trace_id=self.trace_id,
            name=name,
            parent_id=parent_id,
            start_time=start_time,
            input=serialized_input,
            data=serialized_data,
        )

        for processor in self.processors:
            processor.on_span_start(span)

        return span

    def end_span(
        self,
        span: Span,
    ) -> Span:
        """
        End a span by updating it with any changes made to the span object.

        Args:
            span: The span object to update.

        Returns:
            The updated span.
        """
        if span.end_time is None:
            span.end_time = datetime.now(UTC)

        span.input = recursive_model_dump(span.input) if span.input else None
        span.output = recursive_model_dump(span.output) if span.output else None
        span.data = recursive_model_dump(span.data) if span.data else None

        for processor in self.processors:
            processor.on_span_end(span)

        return span

    def get_span(self, span_id: str) -> Span:
        """
        Get a span by ID.

        Args:
            span_id: The ID of the span to get.

        Returns:
            The requested span.
        """
        # Query from Agentex API
        span = self.client.spans.retrieve(span_id)
        return span

    def list_spans(self) -> list[Span]:
        """
        List all spans in this trace.

        Returns:
            List of spans in this trace.
        """
        # Query from Agentex API
        spans = self.client.spans.list(trace_id=self.trace_id)
        return spans

    @contextmanager
    def span(
        self,
        name: str,
        parent_id: str | None = None,
        input: dict[str, Any] | list[dict[str, Any]] | BaseModel | None = None,
        data: dict[str, Any] | list[dict[str, Any]] | BaseModel | None = None,
    ):
        """
        Context manager for spans.
        If trace_id is falsy, acts as a no-op context manager.
        """
        if not self.trace_id:
            yield None
            return
        span = self.start_span(name, parent_id, input, data)
        try:
            yield span
        finally:
            self.end_span(span)


class AsyncTrace:
    """
    AsyncTrace is a wrapper around the Agentex API for tracing.
    It provides a context manager for spans and a way to start and end spans.
    It also provides a way to get spans by ID and list all spans in a trace.
    """

    def __init__(
        self,
        processors: list[AsyncTracingProcessor],
        client: AsyncAgentex,
        trace_id: str | None = None,
    ):
        """
        Initialize a new trace with the specified trace ID.

        Args:
            trace_id: Required trace ID to use for this trace.
            processors: Optional list of tracing processors to use for this trace.
        """
        self.processors = processors
        self.client = client
        self.trace_id = trace_id

    async def start_span(
        self,
        name: str,
        parent_id: str | None = None,
        input: dict[str, Any] | list[dict[str, Any]] | BaseModel | None = None,
        data: dict[str, Any] | list[dict[str, Any]] | BaseModel | None = None,
    ) -> Span:
        """
        Start a new span and register it with the API.

        Args:
            name: Name of the span.
            parent_id: Optional parent span ID.
            input: Optional input data for the span.
            data: Optional additional data for the span.

        Returns:
            The newly created span.
        """
        if not self.trace_id:
            raise ValueError("Trace ID is required to start a span")

        # Create a span using the client's spans resource
        start_time = datetime.now(UTC)

        serialized_input = recursive_model_dump(input) if input else None
        serialized_data = recursive_model_dump(data) if data else None
        id = str(uuid.uuid4())

        span = Span(
            id=id,
            trace_id=self.trace_id,
            name=name,
            parent_id=parent_id,
            start_time=start_time,
            input=serialized_input,
            data=serialized_data,
        )

        if self.processors:
            await asyncio.gather(
                *[processor.on_span_start(span) for processor in self.processors]
            )

        return span

    async def end_span(
        self,
        span: Span,
    ) -> Span:
        """
        End a span by updating it with any changes made to the span object.

        Args:
            span: The span object to update.

        Returns:
            The updated span.
        """
        if span.end_time is None:
            span.end_time = datetime.now(UTC)

        span.input = recursive_model_dump(span.input) if span.input else None
        span.output = recursive_model_dump(span.output) if span.output else None
        span.data = recursive_model_dump(span.data) if span.data else None

        if self.processors:
            await asyncio.gather(
                *[processor.on_span_end(span) for processor in self.processors]
            )

        return span

    async def get_span(self, span_id: str) -> Span:
        """
        Get a span by ID.

        Args:
            span_id: The ID of the span to get.

        Returns:
            The requested span.
        """
        # Query from Agentex API
        span = await self.client.spans.retrieve(span_id)
        return span

    async def list_spans(self) -> list[Span]:
        """
        List all spans in this trace.

        Returns:
            List of spans in this trace.
        """
        # Query from Agentex API
        spans = await self.client.spans.list(trace_id=self.trace_id)
        return spans

    @asynccontextmanager
    async def span(
        self,
        name: str,
        parent_id: str | None = None,
        input: dict[str, Any] | list[dict[str, Any]] | BaseModel | None = None,
        data: dict[str, Any] | list[dict[str, Any]] | BaseModel | None = None,
    ) -> AsyncGenerator[Span | None, None]:
        """
        Context manager for spans.

        Args:
            name: Name of the span.
            parent_id: Optional parent span ID.
            input: Optional input data for the span.
            data: Optional additional data for the span.

        Yields:
            The span object.
        """
        if not self.trace_id:
            yield None
            return
        span = await self.start_span(name, parent_id, input, data)
        try:
            yield span
        finally:
            await self.end_span(span)
