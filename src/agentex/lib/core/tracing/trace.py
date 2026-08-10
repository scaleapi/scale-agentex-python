from __future__ import annotations

import uuid
from typing import Any, AsyncGenerator
from datetime import UTC, datetime
from contextlib import contextmanager, asynccontextmanager
from collections import OrderedDict

from pydantic import BaseModel

from agentex import Agentex, AsyncAgentex
from agentex.types.span import Span
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import recursive_model_dump
from agentex.lib.core.tracing.obs_ids import obs_correlation
from agentex.lib.core.tracing.obs_span import (
    ObsSpanHandle,
    open_obs_span,
    close_obs_span,
    tag_ambient_obs_span,
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
#
# Bounded (OrderedDict + cap): a correct start_span/end_span pair pops its own
# entry, so the registry normally hovers near the live-span count. The cap only
# bites when a caller starts a span and never ends it -- adk.tracing.start_span /
# end_span are public, unpaired API, so a caller-side bug (crash / early return
# between start and end) would otherwise grow this unbounded in a long-lived ACP
# process. Past the cap we evict+close the OLDEST handle so the leak degrades
# gracefully instead of OOMing (and the evicted span still .end()s -> exports).
_OBS_HANDLES_MAX = 2048
_OBS_HANDLES: OrderedDict[str, ObsSpanHandle] = OrderedDict()


def _register_obs_handle(span_id: str, handle: ObsSpanHandle) -> None:
    """Register an open obs wrapper handle, bounding the registry at
    ``_OBS_HANDLES_MAX``. When over the cap, evict and close the oldest handle
    first. close_obs_span is best-effort (detach may warn since it runs on a
    different stack than the attach) and always .end()s the span, so an evicted
    span still exports rather than dangling."""
    _OBS_HANDLES[span_id] = handle
    _OBS_HANDLES.move_to_end(span_id)
    while len(_OBS_HANDLES) > _OBS_HANDLES_MAX:
        _evicted_id, evicted = _OBS_HANDLES.popitem(last=False)
        logger.warning(
            "obs handle registry over cap (%d); evicting+closing oldest span %r. "
            "This means a caller started a span without ending it.",
            _OBS_HANDLES_MAX,
            _evicted_id,
        )
        close_obs_span(evicted)


def _run_on_span_start(processor: SyncTracingProcessor, span: Span) -> None:
    """Invoke ``on_span_start`` such that a processor bug can NEVER crash the app.

    Observability must degrade, not propagate: if this raised, the caller's
    start_span would never return, the caller would never end_span, and the obs
    handle would leak (dict entry + attached OTel context + unended span). By
    swallowing here, start_span returns normally and the standard end_span path
    pops and closes the handle -- no leak, no app-path failure."""
    try:
        processor.on_span_start(span)
    except Exception:
        logger.warning(
            "on_span_start raised for processor %r; skipping (observability must not fail the app path)",
            type(processor).__name__,
            exc_info=True,
        )


def _run_on_span_end(processor: SyncTracingProcessor, span: Span) -> None:
    """Invoke ``on_span_end`` such that a processor bug can NEVER crash the app.

    Symmetric with :func:`_run_on_span_start`. The obs wrapper is already closed
    before this runs (see end_span), so this only guards the app path against a
    buggy processor -- there is no handle left to leak here."""
    try:
        processor.on_span_end(span)
    except Exception:
        logger.warning(
            "on_span_end raised for processor %r; skipping (observability must not fail the app path)",
            type(processor).__name__,
            exc_info=True,
        )


def _in_tracing_dispatch_activity() -> bool:
    """True only when running inside the SDK's OWN dispatched START_SPAN / END_SPAN
    activity (the ``in_temporal_workflow()`` path, where a workflow runs span start
    and end as SEPARATE activities that Temporal can route to different workers).

    That is the one case a per-step obs wrapper can't work: the wrapper opened in
    the START_SPAN activity could never be closed by the END_SPAN activity. A span
    created directly inside a *business* activity (an agent turn's own
    ``adk.tracing.span``) runs start AND end in the same activity process, so a
    wrapper there is safe -- it nests under the interceptor's ambient RunActivity
    span and closes in-process. The tracing dispatch activities are named
    ``start-span`` / ``end-span`` (``TracingActivityName``). Never raises; False
    when temporalio isn't importable or we're not in an activity."""
    try:
        from temporalio import activity

        if not activity.in_activity():
            return False
        return activity.info().activity_type in ("start-span", "end-span")
    except Exception:
        return False


def _in_temporal_activity() -> bool:
    """True inside ANY Temporal activity. There the ambient span is the temporalio
    OTel ``TracingInterceptor`` span REGARDLESS of ``SGP_OBS_MODE``, so callers
    prefer OTel for both the wrapper backend and the correlation read: a plain
    ``dd_only`` read would target ddtrace, which has no request context in a worker
    (no inbound HTTP), so ``open_obs_span`` would return None and the fallback ids
    would be empty -- the business span would persist with no obs_* ids at all.
    Never raises; False when temporalio isn't importable or we're not in an
    activity."""
    try:
        from temporalio import activity

        return activity.in_activity()
    except Exception:
        return False


def _begin_obs(
    name: str,
    span_id: str,
    trace_id: str | None,
) -> tuple[ObsSpanHandle | None, dict[str, str]]:
    """Open the obs wrapper for a business span and return ``(handle, correlation)``.

    Shared by ``Trace.start_span`` and ``AsyncTrace.start_span`` so the two paths
    can't drift. The wrapper is named for the step so ``obs_span_id`` is
    stable/meaningful (not an arbitrary innermost httpx span), and it carries the
    reverse tag (business span/trace id) for the obs -> business pivot.

    We open a real per-step wrapper on the sync path AND inside a *business*
    Temporal activity -- there the wrapper nests under the interceptor's ambient
    RunActivity span and start/end run in-process, so it closes cleanly and each
    business step gets its own obs span (1:1), just like sync.

    The ONE exception is the SDK's own dispatched START_SPAN / END_SPAN activity
    (a workflow calling ``adk.tracing`` -- see ``_in_tracing_dispatch_activity``):
    there start and end are separate activities on possibly different workers, so
    a wrapper could never be closed. We fall back to tagging the ambient
    interceptor span instead, with ``prefer_otel=True`` (the interceptor span is
    OTel regardless of ``SGP_OBS_MODE``, so a plain ``dd_only`` read would
    otherwise point at an unrelated ddtrace span).

    Inside ANY activity we also pass ``prefer_otel`` to the wrapper and the ambient
    fallback: the ambient span is the interceptor's OTel span regardless of mode,
    so a per-step OTel wrapper nests under it and yields valid ids, whereas the
    default ``dd_only`` path would open a ddtrace wrapper -- which finds no request
    context in a worker and returns None, leaving the business span with empty
    obs_* ids.
    """
    if _in_tracing_dispatch_activity():
        tag_ambient_obs_span(business_span_id=span_id, business_trace_id=trace_id, prefer_otel=True)
        return None, obs_correlation(prefer_otel=True)
    prefer_otel = _in_temporal_activity()
    handle = open_obs_span(
        name, business_span_id=span_id, business_trace_id=trace_id, prefer_otel=prefer_otel
    )
    correlation = handle.correlation if handle is not None else obs_correlation(prefer_otel=prefer_otel)
    return handle, correlation


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
        # Open the obs wrapper (or tag the ambient Temporal-activity span); see
        # _begin_obs. Business trace_id stays the run-level task id.
        id = str(uuid.uuid4())
        obs_handle, obs = _begin_obs(name, id, self.trace_id)
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
            _register_obs_handle(span.id, obs_handle)

        for processor in self.processors:
            _run_on_span_start(processor, span)

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
            _run_on_span_end(processor, span)

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
        # Open the obs wrapper (or tag the ambient Temporal-activity span); see
        # _begin_obs. Business trace_id stays the run-level task id.
        id = str(uuid.uuid4())
        obs_handle, obs = _begin_obs(name, id, self.trace_id)
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
            _register_obs_handle(span.id, obs_handle)

        # Enqueueing the START event must not crash the app path either (same
        # principle as _run_on_span_start): swallow so start_span still returns
        # and end_span cleans up the handle. The processors' on_span_start runs
        # later on the queue worker, off the request path.
        if self.processors:
            try:
                self._span_queue.enqueue(SpanEventType.START, span.model_copy(deep=True), self.processors)
            except Exception:
                logger.warning(
                    "failed to enqueue START span event; skipping (observability must not fail the app path)",
                    exc_info=True,
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

        # Close the dedicated obs wrapper span; propagate the business-span error
        # (if any) so the obs span reflects failure, not a false green.
        close_obs_span(_OBS_HANDLES.pop(span.id, None), error=get_span_error(span))

        span.input = recursive_model_dump(span.input) if span.input else None
        span.output = recursive_model_dump(span.output) if span.output else None
        span.data = recursive_model_dump(span.data) if span.data else None

        if self.processors:
            try:
                self._span_queue.enqueue(SpanEventType.END, span.model_copy(deep=True), self.processors)
            except Exception:
                logger.warning(
                    "failed to enqueue END span event; skipping (observability must not fail the app path)",
                    exc_info=True,
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
