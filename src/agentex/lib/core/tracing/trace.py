from __future__ import annotations

import os
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
from sgp_obs.traces import (
    ObsMode,
    SpanError,
    Correlator,
    BusinessRef,
    SpanRequest,
    BusinessSource,
    temporal as _sgp_temporal,
)
from sgp_obs.traces.ports import ObsSpanHandle
from sgp_obs.traces.backends.otel import OTelBackend
from sgp_obs.traces.backends.ddtrace import DDTraceBackend
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

# Stateless sgp_obs backend singletons + the SGP_OBS_MODE -> sgp_obs.ObsMode map.
# The SDK spells the OTel mode "lgtm"; sgp_obs spells it ObsMode.OTEL.
_OTEL = OTelBackend()
_DDTRACE = DDTraceBackend()


def _obs_mode() -> ObsMode:
    """``SGP_OBS_MODE`` mapped to ``sgp_obs.ObsMode`` (``lgtm`` -> OTEL, else DD_ONLY)."""
    return ObsMode.OTEL if (os.getenv("SGP_OBS_MODE") or "").strip().lower() == "lgtm" else ObsMode.DD_ONLY


def _close_obs(handle: ObsSpanHandle | None, error: dict[str, str] | None = None) -> None:
    """Close a wrapper span (best-effort), marking it errored when the business span
    carried an error. Safe on ``None``; obs must never fail the app path."""
    if handle is None:
        return
    try:
        handle.close(SpanError(type=error.get("type"), message=error.get("message")) if error else None)
    except Exception:  # pragma: no cover - best-effort
        pass


# Live per-business-span obs wrapper spans, keyed by the (uuid4) business span id,
# in a MODULE-LEVEL registry -- deliberately NOT on the Trace/AsyncTrace instance.
# TracingService creates a FRESH trace object for every call
# (`self._tracer.trace(trace_id)` in both start_span and end_span), so an
# instance-local dict loses the handle between start and end: end_span's new
# instance can't find it, _close_obs(None) is a no-op, and the OTel wrapper
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
    first. _close_obs is best-effort (detach may warn since it runs on a
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
        _close_obs(evicted)


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

    The whole wrapper-vs-ambient decision + backend selection is the sgp_obs
    ``Correlator``'s job: on the SDK's own dispatched start-span/end-span activity
    (``is_dispatch_boundary``) it tags the ambient interceptor span instead of
    opening a wrapper that could never be closed; elsewhere it opens a per-step
    wrapper. Fail-open — obs must never break the business span.
    """
    req = SpanRequest(
        name=name,
        business=BusinessRef(trace_id=trace_id, span_id=span_id or "", source=BusinessSource.AGENTEX),
        in_activity=_sgp_temporal.in_activity(),
        is_dispatch_boundary=_sgp_temporal.in_dispatch_boundary(),
    )
    try:
        handle, edge = Correlator(_OTEL, _DDTRACE, _obs_mode()).begin(req)
    except Exception:  # pragma: no cover - obs must never break the business span
        return None, {}
    return handle, edge.as_metadata()


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
        _close_obs(_OBS_HANDLES.pop(span.id, None), get_span_error(span))

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
        _close_obs(_OBS_HANDLES.pop(span.id, None), get_span_error(span))

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
