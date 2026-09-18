from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING
from threading import Lock

from agentex.lib.types.tracing import TracingProcessorConfig
from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
    SGPSyncTracingProcessor,
    SGPAsyncTracingProcessor,
)
from agentex.lib.core.tracing.processors.tracing_processor_interface import (
    SyncTracingProcessor,
    AsyncTracingProcessor,
)

if TYPE_CHECKING:
    from agentex.lib.core.tracing.processors.agentex_tracing_processor import (  # noqa: F401
        AgentexSyncTracingProcessor,
        AgentexAsyncTracingProcessor,
    )


class TracingProcessorManager:
    def __init__(self):
        # Mapping of processor config type to processor class
        # Use lazy loading for agentex processors to avoid circular imports
        self.sync_config_registry: dict[str, type[SyncTracingProcessor]] = {
            "sgp": SGPSyncTracingProcessor,
        }
        self.async_config_registry: dict[str, type[AsyncTracingProcessor]] = {
            "sgp": SGPAsyncTracingProcessor,
        }
        # Cache for processors
        self.sync_processors: list[SyncTracingProcessor] = []
        self.async_processors: list[AsyncTracingProcessor] = []
        self.lock = Lock()
        self._agentex_registered = False

    def _ensure_agentex_registered(self):
        """Lazily register agentex processors to avoid circular imports."""
        if not self._agentex_registered:
            from agentex.lib.core.tracing.processors.agentex_tracing_processor import (
                AgentexSyncTracingProcessor,
                AgentexAsyncTracingProcessor,
            )
            self.sync_config_registry["agentex"] = AgentexSyncTracingProcessor
            self.async_config_registry["agentex"] = AgentexAsyncTracingProcessor
            self._agentex_registered = True

    def add_processor_config(self, processor_config: TracingProcessorConfig) -> None:
        with self.lock:
            self._ensure_agentex_registered()
            sync_processor = self.sync_config_registry[processor_config.type]
            async_processor = self.async_config_registry[processor_config.type]
            self.sync_processors.append(sync_processor(processor_config))
            self.async_processors.append(async_processor(processor_config))

    def set_processor_configs(self, processor_configs: list[TracingProcessorConfig]):
        with self.lock:
            for processor_config in processor_configs:
                self.add_processor_config(processor_config)

    def get_sync_processors(self) -> list[SyncTracingProcessor]:
        return self.sync_processors

    def get_async_processors(self) -> list[AsyncTracingProcessor]:
        return self.async_processors


# Global instance
GLOBAL_TRACING_PROCESSOR_MANAGER = TracingProcessorManager()

add_tracing_processor_config = GLOBAL_TRACING_PROCESSOR_MANAGER.add_processor_config
set_tracing_processor_configs = GLOBAL_TRACING_PROCESSOR_MANAGER.set_processor_configs

def get_sync_tracing_processors():
    return GLOBAL_TRACING_PROCESSOR_MANAGER.get_sync_processors()

def get_async_tracing_processors():
    return GLOBAL_TRACING_PROCESSOR_MANAGER.get_async_processors()


_logger = logging.getLogger(__name__)

# Total wall-clock budget for draining every sync tracing processor. A pod's
# terminationGracePeriodSeconds (30s by default) is shared with the OTel flush that
# follows this, so the drain takes a small slice of it.
SYNC_TRACING_SHUTDOWN_BUDGET_S = 5.0


async def shutdown_sync_tracing_processors(
    budget_s: float = SYNC_TRACING_SHUTDOWN_BUDGET_S,
) -> None:
    """Drain the sync tracing processors' queues at shutdown. Never raises.

    Nothing used to call this. The ACP lifespan drained ``shutdown_default_span_queue``,
    which is the ASYNC path only, so a sync agent dropped whatever business spans were
    still queued when the pod stopped. That matters beyond the lost spans: the business
    span is what an obs span's ``agentex.business_trace_id`` resolves to, so losing it
    breaks the pivot from Tempo back to the SGP store.

    ``SGPSyncTracingProcessor.shutdown`` calls ``flush_queue()``, a BLOCKING HTTP flush
    with retries, so three properties have to hold at once:

    **Off the calling loop.** Awaiting it inline stalls the lifespan, so a slow
    collector could burn the pod's whole termination grace period and stop the OTel
    flush that runs after this — trading a few business spans for all of the OTel ones.

    **Concurrent.** Every processor is started at once and they share one deadline. A
    sequential loop would let the first stalled processor spend the entire budget, so
    later processors were skipped even when they would have finished instantly.

    **On DAEMON threads, not the default executor.** This is the subtle one.
    ``asyncio.wait_for`` stops *awaiting* a thread; it cannot stop the thread. And
    ``asyncio.run`` calls ``loop.shutdown_default_executor()``, which JOINS the default
    executor — as does a private ``ThreadPoolExecutor``, via its atexit hook. So a
    timed-out ``asyncio.to_thread`` flush leaves the process blocked on the very export
    the deadline was meant to escape. Measured: a 10s stalled flush under a 0.25s budget
    returns in 0.25s but the process exits at 10.0s with ``to_thread``, and at 0.25s on
    a daemon thread. A daemon thread is abandoned at interpreter exit, which is what the
    budget promises.
    """
    try:
        processors = get_sync_tracing_processors()
    except Exception:  # pragma: no cover - nothing to drain
        _logger.debug("sync tracing processors unavailable at shutdown", exc_info=True)
        return

    if not processors:
        return

    loop = asyncio.get_running_loop()
    finished: list[threading.Event] = []
    all_done = asyncio.Event()

    def _note_finished() -> None:
        if all(event.is_set() for event in finished):
            all_done.set()

    def _flush(processor: SyncTracingProcessor, event: threading.Event) -> None:
        try:
            processor.shutdown()
        except Exception:
            _logger.warning(
                "%s raised while flushing on shutdown; some business spans may be lost",
                type(processor).__name__,
                exc_info=True,
            )
        finally:
            event.set()
            # The loop may already be closed if we timed out and shutdown raced ahead;
            # abandoning the notification is fine, nobody is waiting on it any more.
            try:
                loop.call_soon_threadsafe(_note_finished)
            except RuntimeError:  # pragma: no cover - loop already closed
                pass

    for index, processor in enumerate(processors):
        event = threading.Event()
        finished.append(event)
        threading.Thread(
            target=_flush,
            args=(processor, event),
            daemon=True,
            name=f"agentex-span-flush-{index}",
        ).start()

    try:
        await asyncio.wait_for(all_done.wait(), budget_s)
    except (TimeoutError, asyncio.TimeoutError):
        stalled = [
            type(processor).__name__
            for processor, event in zip(processors, finished)
            if not event.is_set()
        ]
        _logger.warning(
            "sync tracing shutdown budget of %.1fs expired with %s still flushing; "
            "their business spans are lost, but shutdown continues",
            budget_s,
            ", ".join(stalled) or "unknown processors",
        )
