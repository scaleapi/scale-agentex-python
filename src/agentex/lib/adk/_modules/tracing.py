# ruff: noqa: I001
# Import order matters - AsyncTracer must come after client import to avoid circular imports
from __future__ import annotations
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

from temporalio.common import RetryPolicy

from agentex import AsyncAgentex  # noqa: F401
from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.services.adk.tracing import TracingService
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.temporal.activities.adk.tracing_activities import (
    EndSpanParams,
    StartSpanParams,
    TracingActivityName,
)
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.span import Span
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.utils.temporal import in_temporal_workflow

logger = make_logger(__name__)

DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


class TracingModule:
    """
    Module for managing tracing and span operations in Agentex.
    Provides high-level async methods for starting, ending, and managing spans for distributed tracing.
    """

    def __init__(self, tracing_service: TracingService | None = None):
        """
        Initialize the tracing interface.

        Args:
            tracing_service (Optional[TracingService]): Optional pre-configured tracing service.
                If None, will be lazily created on first use so the httpx client is
                bound to the correct running event loop.
        """
        self._tracing_service_explicit = tracing_service
        self._tracing_service_lazy: TracingService | None = None
        self._bound_loop_id: int | None = None

    @property
    def _tracing_service(self) -> TracingService:
        if self._tracing_service_explicit is not None:
            return self._tracing_service_explicit

        import asyncio

        # Determine the current event loop (if any).
        try:
            loop = asyncio.get_running_loop()
            loop_id = id(loop)
        except RuntimeError:
            loop_id = None

        # Re-create the underlying httpx client when the event loop changes
        # (e.g. between HTTP requests in a sync ASGI server) to avoid
        # "Event loop is closed" / "bound to a different event loop" errors.
        if self._tracing_service_lazy is None or (
            loop_id is not None and loop_id != self._bound_loop_id
        ):
            import httpx

            # Disable keepalive so each span HTTP call gets a fresh TCP
            # connection.  Reused connections carry asyncio primitives bound
            # to the event loop that created them; in sync-ACP / streaming
            # contexts the loop context can shift between calls, causing
            # "bound to a different event loop" RuntimeErrors.
            agentex_client = create_async_agentex_client(
                http_client=httpx.AsyncClient(
                    limits=httpx.Limits(max_keepalive_connections=0),
                ),
            )
            tracer = AsyncTracer(agentex_client)
            self._tracing_service_lazy = TracingService(tracer=tracer)
            self._bound_loop_id = loop_id

        return self._tracing_service_lazy

    @asynccontextmanager
    async def span(
        self,
        trace_id: str,
        name: str,
        input: list[Any] | dict[str, Any] | BaseModel | None = None,
        data: list[Any] | dict[str, Any] | BaseModel | None = None,
        parent_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> AsyncGenerator[Span | None, None]:
        """
        Async context manager for creating and automatically closing a span.
        Yields the started span object. The span is automatically ended when the context exits.

        If trace_id is falsy, acts as a no-op context manager.

        Args:
            trace_id (str): The trace ID for the span.
            name (str): The name of the span.
            input (Union[List, Dict, BaseModel]): The input for the span.
            parent_id (Optional[str]): The parent span ID for the span.
            data (Optional[Union[List, Dict, BaseModel]]): The data for the span.
            start_to_close_timeout (timedelta): The start to close timeout for the span.
            heartbeat_timeout (timedelta): The heartbeat timeout for the span.
            retry_policy (RetryPolicy): The retry policy for the span.

        Returns:
            AsyncGenerator[Optional[Span], None]: An async generator that yields the started span object.
        """
        if not trace_id:
            yield None
            return

        span: Span | None = await self.start_span(
            trace_id=trace_id,
            name=name,
            input=input,
            parent_id=parent_id,
            data=data,
            start_to_close_timeout=start_to_close_timeout,
            heartbeat_timeout=heartbeat_timeout,
            retry_policy=retry_policy,
        )
        try:
            yield span
        finally:
            if span:
                await self.end_span(
                    trace_id=trace_id,
                    span=span,
                    start_to_close_timeout=start_to_close_timeout,
                    heartbeat_timeout=heartbeat_timeout,
                    retry_policy=retry_policy,
                )

    async def start_span(
        self,
        trace_id: str,
        name: str,
        input: list[Any] | dict[str, Any] | BaseModel | None = None,
        parent_id: str | None = None,
        data: list[Any] | dict[str, Any] | BaseModel | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=1),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> Span | None:
        """
        Start a new span in the trace.

        Args:
            trace_id (str): The trace ID for the span.
            name (str): The name of the span.
            input (Union[List, Dict, BaseModel]): The input for the span.
            parent_id (Optional[str]): The parent span ID for the span.
            data (Optional[Union[List, Dict, BaseModel]]): The data for the span.
            start_to_close_timeout (timedelta): The start to close timeout for the span.
            heartbeat_timeout (timedelta): The heartbeat timeout for the span.
            retry_policy (RetryPolicy): The retry policy for the span.

        Returns:
            Span: The started span object.
        """
        params = StartSpanParams(
            trace_id=trace_id,
            parent_id=parent_id,
            name=name,
            input=input,
            data=data,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=TracingActivityName.START_SPAN,
                request=params,
                response_type=Span,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._tracing_service.start_span(
                trace_id=trace_id,
                name=name,
                input=input,
                parent_id=parent_id,
                data=data,
            )

    async def end_span(
        self,
        trace_id: str,
        span: Span,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=1),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> Span:
        """
        End an existing span in the trace.

        Args:
            trace_id (str): The trace ID for the span.
            span (Span): The span to end.
            start_to_close_timeout (timedelta): The start to close timeout for the span.
            heartbeat_timeout (timedelta): The heartbeat timeout for the span.
            retry_policy (RetryPolicy): The retry policy for the span.

        Returns:
            Span: The ended span object.
        """
        params = EndSpanParams(
            trace_id=trace_id,
            span=span,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=TracingActivityName.END_SPAN,
                request=params,
                response_type=Span,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._tracing_service.end_span(
                trace_id=trace_id,
                span=span,
            )
