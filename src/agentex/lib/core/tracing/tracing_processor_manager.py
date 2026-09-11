from __future__ import annotations

from threading import RLock

from agentex.lib.types.tracing import TracingProcessorConfig
from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
    SGPSyncTracingProcessor,
    SGPAsyncTracingProcessor,
)
from agentex.lib.core.tracing.processors.tracing_processor_interface import (
    SyncTracingProcessor,
    AsyncTracingProcessor,
)


class TracingProcessorManager:
    def __init__(self):
        self.sync_config_registry: dict[str, type[SyncTracingProcessor]] = {
            "sgp": SGPSyncTracingProcessor,
        }
        self.async_config_registry: dict[str, type[AsyncTracingProcessor]] = {
            "sgp": SGPAsyncTracingProcessor,
        }
        # Cache for processors
        self.sync_processors: list[SyncTracingProcessor] = []
        self.async_processors: list[AsyncTracingProcessor] = []
        # Reentrant: set_processor_configs holds it while calling add_processor_config.
        self.lock = RLock()

    def add_processor_config(self, processor_config: TracingProcessorConfig) -> None:
        with self.lock:
            if processor_config.type not in self.sync_config_registry:
                raise ValueError(
                    f"Unknown tracing processor type {processor_config.type!r}. "
                    f"Supported: {sorted(self.sync_config_registry)}. The Agentex span store "
                    "was removed, configure SGPTracingProcessorConfig instead."
                )
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
