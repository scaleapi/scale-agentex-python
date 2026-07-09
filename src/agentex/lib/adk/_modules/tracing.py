# ruff: noqa: I001
# Import order matters - AsyncTracer must come after client import to avoid circular imports
from __future__ import annotations
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, TimeoutError as TemporalTimeoutError, is_cancelled_exception

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
from agentex.lib.core.tracing.usage import usage_from_counts, validate_usage_blob
from agentex.types.span import Span
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.utils.temporal import in_temporal_workflow

logger = make_logger(__name__)

DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)
TEMPORAL_SPAN_ACTIVITY_DROPPED_METRIC = "agentex.tracing.temporal_span_activity.dropped"


def _record_temporal_span_activity_dropped(event_type: str) -> None:
    try:
        workflow.metric_meter().create_counter(
            TEMPORAL_SPAN_ACTIVITY_DROPPED_METRIC,
            description="Temporal tracing span activities dropped after fail-open",
            unit="1",
        ).add(1, {"event_type": event_type})
    except Exception:
        pass


class TurnSpan:
    """Handle for a turn-level (rollup) span, yielded by ``TracingModule.turn_span``.

    Encapsulates the billing contract so agents cannot double-count usage:
    the turn's aggregate usage goes to ``span.data["usage"]`` (+
    ``span.data["cost_usd"]``) via :meth:`record_usage`. The backend keeps the
    aggregate and de-dups any per-call ``output["usage"]`` children against it.
    Never hand-write usage into ``output`` on a rollup span — that is the
    double-count bug this helper exists to prevent.

    All methods no-op when tracing is disabled (``span`` is None), so agent
    code needs no ``if span:`` guards.
    """

    def __init__(self, span: Span | None):
        self.span = span

    def record_usage(
        self,
        usage: dict[str, Any] | None = None,
        cost_usd: float | None = None,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        cached_input_tokens: int | None = None,
        reasoning_tokens: int | None = None,
    ) -> None:
        """Record the turn's aggregate usage on the span's ``data``.

        Pass either a prebuilt ``usage`` mapping (framework token spellings
        like ``prompt_tokens``/``completion_tokens`` are accepted by the
        backend) or individual token counts, plus an optional ``cost_usd``.
        Individual counts are merged over the ``usage`` mapping. The usage must
        be this turn's own tokens, not a session-cumulative total.
        """
        if self.span is None:
            return

        blob: dict[str, Any] = validate_usage_blob(usage) if usage else {}
        blob.update(
            usage_from_counts(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cached_input_tokens=cached_input_tokens,
                reasoning_tokens=reasoning_tokens,
            )
        )

        if self.span.data is not None and not isinstance(self.span.data, dict):
            logger.warning(
                f"TurnSpan.record_usage: span.data is {type(self.span.data).__name__} "
                "(expected dict or None); existing data will be replaced."
            )
        data = self.span.data if isinstance(self.span.data, dict) else {}
        if blob:
            data["usage"] = blob
        if cost_usd is not None:
            data["cost_usd"] = cost_usd
        self.span.data = data

    @property
    def output(self) -> Any:
        return self.span.output if self.span is not None else None

    @output.setter
    def output(self, value: Any) -> None:
        if self.span is not None:
            self.span.output = value


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
        if self._tracing_service_lazy is None or (loop_id is not None and loop_id != self._bound_loop_id):
            import httpx

            # Keepalive ON: connections are reused within a single event
            # loop, eliminating the TLS-handshake-per-span penalty under
            # load.  Cross-loop safety is preserved by rebuilding the
            # client whenever loop_id changes (the conditional above).
            agentex_client = create_async_agentex_client(
                http_client=httpx.AsyncClient(
                    limits=httpx.Limits(max_keepalive_connections=20),
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
        task_id: str | None = None,
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
            task_id (Optional[str]): The task ID this span belongs to.
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
            task_id=task_id,
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

    @asynccontextmanager
    async def turn_span(
        self,
        trace_id: str,
        name: str,
        input: list[Any] | dict[str, Any] | BaseModel | None = None,
        data: list[Any] | dict[str, Any] | BaseModel | None = None,
        parent_id: str | None = None,
        task_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> AsyncGenerator[TurnSpan, None]:
        """Span for one agent turn, with usage recorded as the billable aggregate.

        Same lifecycle as :meth:`span`, but yields a :class:`TurnSpan` whose
        ``record_usage(usage=..., cost_usd=...)`` writes the turn's rollup
        usage to ``span.data`` — the shape the backend bills once per turn.
        Per-call child spans (LLM adapters) may still carry
        ``output["usage"]``; the backend de-dups them against this aggregate.

        Example::

            async with adk.tracing.turn_span(trace_id=task.id, name="turn", input={...}, task_id=task.id) as turn:
                result = await run_llm_calls()
                turn.output = {"response": result.text}
                turn.record_usage(usage=result.usage, cost_usd=result.cost_usd)
        """
        async with self.span(
            trace_id=trace_id,
            name=name,
            input=input,
            data=data,
            parent_id=parent_id,
            task_id=task_id,
            start_to_close_timeout=start_to_close_timeout,
            heartbeat_timeout=heartbeat_timeout,
            retry_policy=retry_policy,
        ) as span:
            yield TurnSpan(span)

    async def start_span(
        self,
        trace_id: str,
        name: str,
        input: list[Any] | dict[str, Any] | BaseModel | None = None,
        parent_id: str | None = None,
        data: list[Any] | dict[str, Any] | BaseModel | None = None,
        task_id: str | None = None,
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
            task_id (Optional[str]): The task ID this span belongs to.
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
            task_id=task_id,
        )
        if in_temporal_workflow():
            try:
                return await ActivityHelpers.execute_activity(
                    activity_name=TracingActivityName.START_SPAN,
                    request=params,
                    response_type=Span,
                    start_to_close_timeout=start_to_close_timeout,
                    retry_policy=retry_policy,
                    heartbeat_timeout=heartbeat_timeout,
                )
            except (ActivityError, TemporalTimeoutError) as err:
                if is_cancelled_exception(err):
                    raise
                workflow.logger.warning(
                    "Failed to start tracing span %r for trace_id=%r; continuing without tracing",
                    name,
                    trace_id,
                    exc_info=True,
                )
                _record_temporal_span_activity_dropped("start")
                return None
        else:
            return await self._tracing_service.start_span(
                trace_id=trace_id,
                name=name,
                input=input,
                parent_id=parent_id,
                data=data,
                task_id=task_id,
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
            try:
                return await ActivityHelpers.execute_activity(
                    activity_name=TracingActivityName.END_SPAN,
                    request=params,
                    response_type=Span,
                    start_to_close_timeout=start_to_close_timeout,
                    retry_policy=retry_policy,
                    heartbeat_timeout=heartbeat_timeout,
                )
            except (ActivityError, TemporalTimeoutError) as err:
                if is_cancelled_exception(err):
                    raise
                workflow.logger.warning(
                    "Failed to end tracing span %r for trace_id=%r; continuing without closing trace",
                    span.id,
                    trace_id,
                    exc_info=True,
                )
                _record_temporal_span_activity_dropped("end")
                return span
        else:
            return await self._tracing_service.end_span(
                trace_id=trace_id,
                span=span,
            )
