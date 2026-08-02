from __future__ import annotations

import uuid
from typing import Any, AsyncGenerator
from datetime import UTC, datetime
from contextlib import contextmanager, asynccontextmanager

from pydantic import BaseModel

from agentex import Agentex, AsyncAgentex
from agentex.types.span import Span
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import recursive_model_dump
from agentex.lib.core.tracing.obs_ids import obs_correlation
from agentex.lib.core.tracing.obs_span import (
    ObsSpanHandle,
    close_obs_span,
    open_obs_span,
)
from agentex.lib.core.tracing.span_error import get_span_error, set_span_error
from agentex.lib.core.tracing.span_queue import (
    SpanEventType,
    AsyncSpanQueue,
    get_default_span_queue,
)
from agentex.lib.core.tracing.processors.tracing_processor_interface import (
    SyncTracingProcessor,
    AsyncTracingProcessor,
)

logger = make_logger(__name__)

# Live per-business-span obs wrapper spans, keyed by the (uuid4) business span id,
# in a MODULE-LEVEL registry -- deliberately NOT on the Trace/AsyncTrace instance.
# TracingService creates a FRESH trace object for every call
# (`self._tracer.trace(trace_id)` in both start_span and end_span), so an
# instance-local dict loses the handle between start and end: end_span's new
# instance can't find it, close_obs_span(None) is a no-op, and the OTel wrapper
# span is never .end()ed -> never exported (Simple/Batch processors only emit on
# end). A module-level dict keyed by the unique span id survives across instances;
# uuid4 span ids cannot collide across concurrent traces.
_OBS_HANDLES: dict[str, ObsSpanHandle] = {}


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
        # Obs wrapper spans are tracked in the module-level _OBS_HANDLES registry
        # (see comment there): a fresh trace object is created per start/end call,
        # so the handle must not live on the instance.

    def start_span(
        self,
        name: str,
        parent_id: str | None = None,
        input: dict[str, Any] | list[dict[str, Any]] | BaseModel | None = None,
        data: dict[str, Any] | list[dict[str, Any]] | BaseModel | None = None,
        task_id: str | None = None,
    ) -> Span:
        """
        Start a new span and register it with the API.

        Args:
            name: Name of the span.
            parent_id: Optional parent span ID.
            input: Optional input data for the span.
            data: Optional additional data for the span.
            task_id: Optional ID of the task this span belongs to.

        Returns:
            The newly created span.
        """

        if not self.trace_id:
            raise ValueError("Trace ID is required to start a span")

        # Create a span using the client's spans resource
        start_time = datetime.now(UTC)

        serialized_input = recursive_model_dump(input) if input else None
        serialized_data = recursive_model_dump(data) if data else None
        # Open a dedicated obs wrapper span named for this step and make it
        # active, so obs_span_id is stable/meaningful (not an arbitrary innermost
        # httpx span). It also carries the reverse tag (business span/trace id)
        # so you can pivot obs -> business in Tempo/DD. Falls back to the ambient
        # obs context (ddtrace) when not in lgtm mode. Business trace_id stays the
        # run-level task id.
        id = str(uuid.uuid4())
        obs_handle = open_obs_span(
            name, business_span_id=id, business_trace_id=self.trace_id
        )
        obs = obs_handle.correlation if obs_handle is not None else obs_correlation()
        if obs:
            serialized_data = {**(serialized_data or {}), **obs}

        span = Span(
            id=id,
            trace_id=self.trace_id,
            name=name,
            parent_id=parent_id,
            start_time=start_time,
            input=serialized_input,
            data=serialized_data,
            task_id=task_id,
        )
        if obs_handle is not None:
            _OBS_HANDLES[span.id] = obs_handle

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

        # Close the dedicated obs wrapper span; propagate the business-span error
        # (if any) so the obs span reflects failure, not a false green.
        close_obs_span(_OBS_HANDLES.pop(span.id, None), error=get_span_error(span))

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
        task_id: str | None = None,
    ):
        """
        Context manager for spans.
        If trace_id is falsy, acts as a no-op context manager.
        """
        if not self.trace_id:
            yield None
            return
        span = self.start_span(name, parent_id, input, data, task_id=task_id)
        try:
            yield span
        except Exception as exc:
            set_span_error(span, exc)
            raise
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
        span_queue: AsyncSpanQueue | None = None,
    ):
        """
        Initialize a new trace with the specified trace ID.

        Args:
            trace_id: Required trace ID to use for this trace.
            processors: Optional list of tracing processors to use for this trace.
            span_queue: Optional span queue for background processing.
        """
        self.processors = processors
        self.client = client
        self.trace_id = trace_id
        self._span_queue = span_queue or get_default_span_queue()
        # Obs wrapper spans are tracked in the module-level _OBS_HANDLES registry
        # (see comment there): a fresh trace object is created per start/end call,
        # so the handle must not live on the instance.

    async def start_span(
        self,
        name: str,
        parent_id: str | None = None,
        input: dict[str, Any] | list[dict[str, Any]] | BaseModel | None = None,
        data: dict[str, Any] | list[dict[str, Any]] | BaseModel | None = None,
        task_id: str | None = None,
    ) -> Span:
        """
        Start a new span and register it with the API.

        Args:
            name: Name of the span.
            parent_id: Optional parent span ID.
            input: Optional input data for the span.
            data: Optional additional data for the span.
            task_id: Optional ID of the task this span belongs to.

        Returns:
            The newly created span.
        """
        if not self.trace_id:
            raise ValueError("Trace ID is required to start a span")

        # Create a span using the client's spans resource
        start_time = datetime.now(UTC)

        serialized_input = recursive_model_dump(input) if input else None
        serialized_data = recursive_model_dump(data) if data else None
        # Open a dedicated obs wrapper span named for this step and make it
        # active, so obs_span_id is stable/meaningful (not an arbitrary innermost
        # httpx span). It also carries the reverse tag (business span/trace id)
        # so you can pivot obs -> business in Tempo/DD. Falls back to the ambient
        # obs context (ddtrace) when not in lgtm mode. Business trace_id stays the
        # run-level task id.
        id = str(uuid.uuid4())
        obs_handle = open_obs_span(
            name, business_span_id=id, business_trace_id=self.trace_id
        )
        obs = obs_handle.correlation if obs_handle is not None else obs_correlation()
        if obs:
            serialized_data = {**(serialized_data or {}), **obs}

        span = Span(
            id=id,
            trace_id=self.trace_id,
            name=name,
            parent_id=parent_id,
            start_time=start_time,
            input=serialized_input,
            data=serialized_data,
            task_id=task_id,
        )
        if obs_handle is not None:
            _OBS_HANDLES[span.id] = obs_handle

        if self.processors:
            self._span_queue.enqueue(SpanEventType.START, span.model_copy(deep=True), self.processors)

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

        # Close the dedicated obs wrapper span; propagate the business-span error
        # (if any) so the obs span reflects failure, not a false green.
        close_obs_span(_OBS_HANDLES.pop(span.id, None), error=get_span_error(span))

        span.input = recursive_model_dump(span.input) if span.input else None
        span.output = recursive_model_dump(span.output) if span.output else None
        span.data = recursive_model_dump(span.data) if span.data else None

        if self.processors:
            self._span_queue.enqueue(SpanEventType.END, span.model_copy(deep=True), self.processors)

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
        task_id: str | None = None,
    ) -> AsyncGenerator[Span | None, None]:
        """
        Context manager for spans.

        Args:
            name: Name of the span.
            parent_id: Optional parent span ID.
            input: Optional input data for the span.
            data: Optional additional data for the span.
            task_id: Optional ID of the task this span belongs to.

        Yields:
            The span object.
        """
        if not self.trace_id:
            yield None
            return
        span = await self.start_span(name, parent_id, input, data, task_id=task_id)
        try:
            yield span
        except Exception as exc:
            set_span_error(span, exc)
            raise
        finally:
            await self.end_span(span)
