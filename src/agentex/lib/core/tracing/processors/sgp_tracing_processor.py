from __future__ import annotations

import asyncio
from typing import Optional, override

import scale_gp_beta.lib.tracing as tracing
from scale_gp_beta import APIError, SGPClient, AsyncSGPClient
from scale_gp_beta.lib.tracing import create_span, flush_queue
from scale_gp_beta.lib.tracing.span import Span as SGPSpan

from agentex.types.span import Span
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.tracing.processors.tracing_processor_interface import (
    SyncTracingProcessor,
    AsyncTracingProcessor,
)

logger = make_logger(__name__)


# Mirrored from scale_gp_beta.lib.tracing.trace_queue_manager defaults so the
# async processor batches and retries the same way the sync (daemon-thread)
# path does.
DEFAULT_MAX_QUEUE_SIZE = 4_000
DEFAULT_TRIGGER_QUEUE_SIZE = 200
DEFAULT_TRIGGER_CADENCE = 4.0
DEFAULT_MAX_BATCH_SIZE = 50
DEFAULT_RETRIES = 4
INITIAL_BACKOFF = 0.4
MAX_BACKOFF = 20.0
SHUTDOWN_DRAIN_TIMEOUT = 10.0


def _get_span_type(span: Span) -> str:
    """Read span_type from span.data['__span_type__'], defaulting to STANDALONE."""
    if isinstance(span.data, dict):
        value = span.data.get("__span_type__", "STANDALONE")
        return str(value)
    return "STANDALONE"


class SGPSyncTracingProcessor(SyncTracingProcessor):
    def __init__(self, config: SGPTracingProcessorConfig):
        disabled = config.sgp_api_key == "" or config.sgp_account_id == ""
        tracing.init(
            SGPClient(
                api_key=config.sgp_api_key,
                account_id=config.sgp_account_id,
                base_url=config.sgp_base_url,
            ),
            disabled=disabled,
        )
        self._spans: dict[str, SGPSpan] = {}
        self.env_vars = EnvironmentVariables.refresh()

    def _add_source_to_span(self, span: Span) -> None:
        if span.data is None:
            span.data = {}
        if isinstance(span.data, dict):
            span.data["__source__"] = "agentex"
            if self.env_vars.ACP_TYPE is not None:
                span.data["__acp_type__"] = self.env_vars.ACP_TYPE
            if self.env_vars.AGENT_NAME is not None:
                span.data["__agent_name__"] = self.env_vars.AGENT_NAME
            if self.env_vars.AGENT_ID is not None:
                span.data["__agent_id__"] = self.env_vars.AGENT_ID

    @override
    def on_span_start(self, span: Span) -> None:
        self._add_source_to_span(span)

        sgp_span = create_span(
            name=span.name,
            span_type=_get_span_type(span),
            span_id=span.id,
            parent_id=span.parent_id,
            trace_id=span.trace_id,
            input=span.input,
            output=span.output,
            metadata=span.data,
        )
        sgp_span.start_time = span.start_time.isoformat()  # type: ignore[union-attr]
        sgp_span.flush(blocking=False)

        self._spans[span.id] = sgp_span

    @override
    def on_span_end(self, span: Span) -> None:
        sgp_span = self._spans.pop(span.id, None)
        if sgp_span is None:
            logger.warning(f"Span {span.id} not found in stored spans, skipping span end")
            return

        self._add_source_to_span(span)
        sgp_span.output = span.output  # type: ignore[assignment]
        sgp_span.metadata = span.data  # type: ignore[assignment]
        sgp_span.end_time = span.end_time.isoformat()  # type: ignore[union-attr]
        sgp_span.flush(blocking=False)

    @override
    def shutdown(self) -> None:
        self._spans.clear()
        flush_queue()


class SGPAsyncTracingProcessor(AsyncTracingProcessor):
    """Async tracing processor that buffers spans and flushes them in batches.

    Mirrors the buffer-plus-flush behavior of the SDK's synchronous
    `TraceQueueManager`, but uses asyncio primitives so it works inside an
    asyncio event loop without blocking it.

    Spans are enqueued on `on_span_start` and `on_span_end`; a background
    `asyncio.Task` worker drains the queue into batches and posts them via
    `client.spans.upsert_batch`. The worker is lazy-initialized on the
    running event loop on first use.
    """

    def __init__(self, config: SGPTracingProcessorConfig):
        self.disabled = config.sgp_api_key == "" or config.sgp_account_id == ""
        self._spans: dict[str, SGPSpan] = {}
        import httpx

        # Disable keepalive so each HTTP call gets a fresh TCP connection,
        # avoiding "bound to a different event loop" errors in sync-ACP.
        self.sgp_async_client = (
            AsyncSGPClient(
                api_key=config.sgp_api_key,
                account_id=config.sgp_account_id,
                base_url=config.sgp_base_url,
                http_client=httpx.AsyncClient(
                    limits=httpx.Limits(max_keepalive_connections=0),
                ),
            )
            if not self.disabled
            else None
        )
        self.env_vars = EnvironmentVariables.refresh()

        # Lazy-initialized on the running loop on first use. Re-created if
        # the loop changes (e.g. sync-ACP / per-request loops) so the worker
        # is always bound to the loop currently consuming it.
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue: Optional[asyncio.Queue[SGPSpan]] = None
        self._worker: Optional[asyncio.Task[None]] = None
        self._shutdown_event: Optional[asyncio.Event] = None
        self._flush_event: Optional[asyncio.Event] = None

        if self.disabled:
            # Log once at init rather than on every span event, which would
            # flood logs at agent throughput.
            logger.warning(
                "SGP tracing is disabled (sgp_api_key or sgp_account_id missing); span events will be ignored"
            )

    def _add_source_to_span(self, span: Span) -> None:
        if span.data is None:
            span.data = {}
        if isinstance(span.data, dict):
            span.data["__source__"] = "agentex"
            if self.env_vars.ACP_TYPE is not None:
                span.data["__acp_type__"] = self.env_vars.ACP_TYPE
            if self.env_vars.AGENT_NAME is not None:
                span.data["__agent_name__"] = self.env_vars.AGENT_NAME
            if self.env_vars.AGENT_ID is not None:
                span.data["__agent_id__"] = self.env_vars.AGENT_ID

    def _ensure_started(self) -> None:
        """Initialize per-loop queue + worker on first use, or after a loop swap.

        Must be called from inside an async method so `get_running_loop()` is
        safe. Idempotent on the same loop while the worker is healthy; on a
        loop change or worker death, it rebuilds the queue and worker (items
        in the previous queue are lost — they were tied to a now-dead loop).
        """
        if self.disabled:
            return
        loop = asyncio.get_running_loop()
        if self._loop is loop and self._worker is not None and not self._worker.done():
            return
        self._loop = loop
        self._queue = asyncio.Queue(maxsize=DEFAULT_MAX_QUEUE_SIZE)
        self._shutdown_event = asyncio.Event()
        self._flush_event = asyncio.Event()
        self._worker = loop.create_task(self._run())

    @override
    async def on_span_start(self, span: Span) -> None:
        self._add_source_to_span(span)
        sgp_span = create_span(
            name=span.name,
            span_type=_get_span_type(span),
            span_id=span.id,
            parent_id=span.parent_id,
            trace_id=span.trace_id,
            input=span.input,
            output=span.output,
            metadata=span.data,
        )
        sgp_span.start_time = span.start_time.isoformat()  # type: ignore[union-attr]
        self._spans[span.id] = sgp_span

        if self.disabled:
            return

        self._ensure_started()
        self._enqueue(sgp_span)

    @override
    async def on_span_end(self, span: Span) -> None:
        sgp_span = self._spans.pop(span.id, None)
        if sgp_span is None:
            logger.warning(f"Span {span.id} not found in stored spans, skipping span end")
            return

        self._add_source_to_span(span)
        sgp_span.output = span.output  # type: ignore[assignment]
        sgp_span.metadata = span.data  # type: ignore[assignment]
        sgp_span.end_time = span.end_time.isoformat()  # type: ignore[union-attr]

        if self.disabled:
            return

        self._ensure_started()
        self._enqueue(sgp_span)

    @override
    async def shutdown(self) -> None:
        # Fast path when the processor was never started (disabled, or
        # shutdown called before any span event).
        if self._worker is None:
            self._spans.clear()
            return

        # Re-enqueue any spans whose end was never recorded so they aren't
        # silently lost. They were already enqueued at start, but on_span_end
        # is what mutates output / metadata / end_timestamp; without a second
        # enqueue, the server only sees the start payload for them.
        for sgp_span in list(self._spans.values()):
            self._enqueue(sgp_span)
        self._spans.clear()

        assert self._shutdown_event is not None
        self._shutdown_event.set()
        if self._flush_event is not None:
            self._flush_event.set()

        try:
            await asyncio.wait_for(self._worker, timeout=SHUTDOWN_DRAIN_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning(f"Async tracing worker did not exit within {SHUTDOWN_DRAIN_TIMEOUT}s; cancelling")
            self._worker.cancel()

    def _enqueue(self, sgp_span: SGPSpan) -> None:
        """Push a span onto the queue and signal an early flush if the queue
        has crossed `DEFAULT_TRIGGER_QUEUE_SIZE`. Drops the span on overflow."""
        if self._queue is None:
            return
        try:
            self._queue.put_nowait(sgp_span)
        except asyncio.QueueFull:
            logger.warning(f"Tracing queue full; dropping span {sgp_span.span_id}")
            return
        if self._flush_event is not None and self._queue.qsize() >= DEFAULT_TRIGGER_QUEUE_SIZE:
            self._flush_event.set()

    def _is_shutting_down(self) -> bool:
        return self._shutdown_event is not None and self._shutdown_event.is_set()

    async def _wait_for_flush_signal(self) -> None:
        """Block until either an early-flush signal arrives or the cadence
        timer fires. Returns either way; the caller is responsible for
        draining."""
        assert self._flush_event is not None
        try:
            await asyncio.wait_for(self._flush_event.wait(), timeout=DEFAULT_TRIGGER_CADENCE)
        except asyncio.TimeoutError:
            pass
        self._flush_event.clear()

    async def _safe_drain(self, log_label: str) -> None:
        """Run `_drain`, catching unexpected errors so one bad iteration
        doesn't kill the worker. CancelledError is always re-raised."""
        try:
            await self._drain()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(log_label)

    async def _run(self) -> None:
        """Background worker. Sleeps until a flush trigger fires, drains the
        queue, and repeats. On shutdown signal, does one final drain so
        nothing pending is dropped. The outermost try / except keeps a worker
        crash from being silent."""
        try:
            while not self._is_shutting_down():
                await self._wait_for_flush_signal()
                await self._safe_drain("Tracing worker iteration failed; continuing")
            await self._safe_drain("Final tracing drain failed; some spans may be lost")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Async tracing worker crashed")

    async def _drain(self) -> None:
        """Pull spans from the queue and upsert them in batches of up to
        `DEFAULT_MAX_BATCH_SIZE`. Stops when the queue is empty.

        A span whose `to_request_params()` raises is dropped (logged); the
        rest of the batch still goes out. This matches the SDK's exporter."""
        if self._queue is None or self.sgp_async_client is None:
            return
        while not self._queue.empty():
            batch: list[dict] = []
            while len(batch) < DEFAULT_MAX_BATCH_SIZE and not self._queue.empty():
                try:
                    sgp_span = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                try:
                    batch.append(sgp_span.to_request_params())
                except Exception:
                    logger.exception("Failed to build span params; dropping span")
            if not batch:
                continue
            await self._upsert_with_retry(batch)

    async def _upsert_with_retry(self, batch: list[dict]) -> None:
        """POST a single batch with the SDK's retry policy: 4 attempts with
        exponential backoff (`INITIAL_BACKOFF` -> `MAX_BACKOFF` capped).

        - `APIError` triggers retry up to `DEFAULT_RETRIES` attempts.
        - Anything else is logged and the batch is dropped (we don't know
          whether the server saw the request, and the SDK already wraps
          transport-level failures as `APIError`)."""
        if self.sgp_async_client is None:
            return
        backoff = INITIAL_BACKOFF
        for attempt in range(DEFAULT_RETRIES):
            try:
                await self.sgp_async_client.spans.upsert_batch(items=batch)  # type: ignore[arg-type]
                return
            except APIError as exc:
                if attempt == DEFAULT_RETRIES - 1:
                    logger.error(f"Failed to export {len(batch)} spans after {DEFAULT_RETRIES} attempts: {exc.message}")
                    return
                logger.warning(f"Span export failed ({exc.message}); retrying in {backoff:.1f}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(f"Unexpected error exporting {len(batch)} spans; dropping batch")
                return
