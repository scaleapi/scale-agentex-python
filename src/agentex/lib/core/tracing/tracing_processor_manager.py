from threading import Lock

from agentex.lib.core.tracing.processors.agentex_tracing_processor import (
    AgentexAsyncTracingProcessor,
    AgentexSyncTracingProcessor,
)
from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
    SGPAsyncTracingProcessor,
    SGPSyncTracingProcessor,
)
from agentex.lib.core.tracing.processors.tracing_processor_interface import (
    AsyncTracingProcessor,
    SyncTracingProcessor,
)
from agentex.lib.types.tracing import AgentexTracingProcessorConfig, TracingProcessorConfig


class TracingProcessorManager:
    def __init__(self):
        # Mapping of processor config type to processor class
        self.sync_config_registry: dict[str, type[SyncTracingProcessor]] = {
            "agentex": AgentexSyncTracingProcessor,
            "sgp": SGPSyncTracingProcessor,
        }
        self.async_config_registry: dict[str, type[AsyncTracingProcessor]] = {
            "agentex": AgentexAsyncTracingProcessor,
            "sgp": SGPAsyncTracingProcessor,
        }
        # Cache for processors
        self.sync_processors: list[SyncTracingProcessor] = []
        self.async_processors: list[AsyncTracingProcessor] = []
        self.lock = Lock()

    def add_processor_config(self, processor_config: TracingProcessorConfig) -> None:
        with self.lock:
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
get_sync_tracing_processors = GLOBAL_TRACING_PROCESSOR_MANAGER.get_sync_processors
get_async_tracing_processors = GLOBAL_TRACING_PROCESSOR_MANAGER.get_async_processors

# Add the Agentex tracing processor by default
add_tracing_processor_config(AgentexTracingProcessorConfig())
