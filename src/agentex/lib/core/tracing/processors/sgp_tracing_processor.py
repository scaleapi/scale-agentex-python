from __future__ import annotations

import asyncio
from typing import Optional, override

import scale_gp_beta.lib.tracing as tracing
from scale_gp_beta import SGPClient, AsyncSGPClient
from scale_gp_beta._exceptions import APIError
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

    The HTTP client, queue, and worker task are lazy-initialized on the
    running event loop the first time a span event is recorded. This avoids
    the "bound to a different event loop" errors that occur when the
    processor is constructed on one loop but used on another (e.g. a worker
    that creates a fresh loop per request) and lets us re-enable HTTP
    keepalive on the underlying httpx client without paying a TCP+TLS
    handshake on every span event.
    """

    def __init__(self, config: SGPTracingProcessorConfig):
        self._config = config
        self.disabled = config.sgp_api_key == "" or config.sgp_account_id == ""
        self._spans: dict[str, SGPSpan] = {}
        self.env_vars = EnvironmentVariables.refresh()

        # Lazy-initialized on the running loop on first use. Holding these
        # as attributes (rather than constructing eagerly in __init__) is
        # what lets the processor survive the loop on which it was created
        # being replaced — a common pattern in sync-ACP / per-request loops.
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.sgp_async_client: Optional[AsyncSGPClient] = None
        # Loop the *processor-owned* client was constructed on. Remains
        # None when the client was injected externally (e.g. by a test);
        # in that case we never replace it.
        self._client_owned_at_loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue: Optional[asyncio.Queue[SGPSpan]] = None
        self._worker: Optional[asyncio.Task[None]] = None
        self._shutdown_event: Optional[asyncio.Event] = None
        self._flush_event: Optional[asyncio.Event] = None

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
        """Initialize per-loop state on first use, or after a loop swap.

        Must be called from inside an async method so `get_running_loop()`
        is safe.
        """
        if self.disabled:
            return
        loop = asyncio.get_running_loop()
        if self._loop is loop and self._worker is not None and not self._worker.done():
            return

        self._loop = loop
        # We construct an httpx-backed client lazily on the running loop so
        # connection pooling and keepalive can be left at httpx defaults
        # without hitting "bound to a different event loop" errors when the
        # processor outlives its original loop. An externally injected
        # client (e.g. a test mock) is left alone — _client_owned_at_loop
        # stays None for those.
        if self.sgp_async_client is None:
            self.sgp_async_client = AsyncSGPClient(
                api_key=self._config.sgp_api_key,
                account_id=self._config.sgp_account_id,
                base_url=self._config.sgp_base_url,
            )
            self._client_owned_at_loop = loop
        elif self._client_owned_at_loop is not None and self._client_owned_at_loop is not loop:
            # We previously created a client on a now-stale loop. Replace it.
            self.sgp_async_client = AsyncSGPClient(
                api_key=self._config.sgp_api_key,
                account_id=self._config.sgp_account_id,
                base_url=self._config.sgp_base_url,
            )
            self._client_owned_at_loop = loop
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
        # shutdown called before any span event). Avoid spinning up a
        # worker just to tear it down.
        if self._worker is None:
            self._spans.clear()
            return

        # Re-enqueue any spans whose end was never recorded so they aren't
        # silently lost. They were already enqueued at start, but on_span_end
        # is what mutates output / metadata / end_timestamp; without a
        # second enqueue, the server only sees the start payload for them.
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
        if self._queue is None:
            return
        try:
            self._queue.put_nowait(sgp_span)
        except asyncio.QueueFull:
            logger.warning(f"Tracing queue full; dropping span {sgp_span.span_id}")
            return
        if self._flush_event is not None and self._queue.qsize() >= DEFAULT_TRIGGER_QUEUE_SIZE:
            self._flush_event.set()

    async def _run(self) -> None:
        try:
            while not (self._shutdown_event and self._shutdown_event.is_set()):
                # Wake on either an early-flush signal or the cadence timer.
                assert self._flush_event is not None
                try:
                    await asyncio.wait_for(self._flush_event.wait(), timeout=DEFAULT_TRIGGER_CADENCE)
                except asyncio.TimeoutError:
                    pass
                self._flush_event.clear()
                # Per-iteration guard: an unexpected error during one drain
                # must not kill the worker, otherwise queued items stay
                # unflushed until shutdown.
                try:
                    await self._drain()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Tracing worker iteration failed; continuing")

            # Final drain on shutdown.
            try:
                await self._drain()
            except Exception:
                logger.exception("Final tracing drain failed; some spans may be lost")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Async tracing worker crashed")

    async def _drain(self) -> None:
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
                # Unexpected error (not APIError, not cancellation): log and
                # drop the batch. We deliberately do not retry because we
                # don't know whether the request reached the server, and
                # the SDK already surfaces transport failures as APIError.
                logger.exception(f"Unexpected error exporting {len(batch)} spans; dropping batch")
                return
