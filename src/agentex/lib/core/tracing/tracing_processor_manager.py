from __future__ import annotations

import asyncio
import logging
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

    Off the event loop and on a deadline, both deliberately.
    ``SGPSyncTracingProcessor.shutdown`` calls ``flush_queue()``, a BLOCKING HTTP flush
    with retries. Calling it inline would stall the caller's loop, so a slow or
    unreachable collector could burn the whole termination grace period and stop the
    OTel flush that runs after it — trading a few business spans for all of the OTel
    ones. Each processor runs in a worker thread, and the budget is shared across all
    of them so one stalled export cannot starve the rest.

    A timed-out flush leaks its thread until the process exits. Accepted: this runs
    only during shutdown, and the alternative is blocking on it.

    Lives here rather than in the ACP server because both entry points need it — the
    ACP server AND the Temporal worker, which runs in its own process.
    """
    try:
        processors = get_sync_tracing_processors()
    except Exception:  # pragma: no cover - nothing to drain
        _logger.debug("sync tracing processors unavailable at shutdown", exc_info=True)
        return

    loop = asyncio.get_running_loop()
    deadline = loop.time() + budget_s

    for processor in processors:
        remaining = deadline - loop.time()
        if remaining <= 0:
            _logger.warning(
                "sync tracing shutdown budget of %.1fs exhausted; %s and any after it "
                "were not flushed and their business spans are lost",
                budget_s,
                type(processor).__name__,
            )
            break
        try:
            await asyncio.wait_for(asyncio.to_thread(processor.shutdown), remaining)
        except (TimeoutError, asyncio.TimeoutError):
            _logger.warning(
                "%s did not flush within the remaining %.1fs; its business spans are "
                "lost, but shutdown continues",
                type(processor).__name__,
                remaining,
            )
        except Exception:  # noqa: PERF203 - one bad processor must not block the rest
            _logger.warning(
                "a sync tracing processor failed to flush on shutdown; "
                "some business spans may be lost",
                exc_info=True,
            )
