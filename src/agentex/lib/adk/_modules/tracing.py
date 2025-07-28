from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

from temporalio.common import RetryPolicy

from agentex import AsyncAgentex
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
            tracing_activities (Optional[TracingActivities]): Optional pre-configured tracing activities. If None, will be auto-initialized.
        """
        if tracing_service is None:
            agentex_client = create_async_agentex_client()
            tracer = AsyncTracer(agentex_client)
            self._tracing_service = TracingService(tracer=tracer)
        else:
            self._tracing_service = tracing_service

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
