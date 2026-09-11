import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.core.tracing.tracing_processor_manager import TracingProcessorManager
from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
    SGPSyncTracingProcessor,
    SGPAsyncTracingProcessor,
)

SGP_MODULE = "agentex.lib.core.tracing.processors.sgp_tracing_processor"


def _sgp_config() -> SGPTracingProcessorConfig:
    return SGPTracingProcessorConfig(sgp_api_key="k", sgp_account_id="a", sgp_base_url="http://sgp.test")


def _patched_sgp():
    env = MagicMock()
    env.refresh.return_value = MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None, AGENT_VERSION=None)
    return (
        patch(f"{SGP_MODULE}.SGPClient"),
        patch(f"{SGP_MODULE}.AsyncSGPClient"),
        patch(f"{SGP_MODULE}.tracing.init"),
        patch(f"{SGP_MODULE}.EnvironmentVariables", env),
    )


def test_unknown_processor_type_is_rejected_by_name():
    manager = TracingProcessorManager()

    with pytest.raises(ValueError, match="agentex.*sgp"):
        manager.add_processor_config(SimpleNamespace(type="agentex"))  # type: ignore[arg-type]

    assert manager.get_sync_processors() == []
    assert manager.get_async_processors() == []


def test_sgp_config_registers_one_sync_and_one_async_processor():
    p1, p2, p3, p4 = _patched_sgp()
    with p1, p2, p3, p4:
        manager = TracingProcessorManager()
        manager.add_processor_config(_sgp_config())

    (sync_processor,) = manager.get_sync_processors()
    (async_processor,) = manager.get_async_processors()
    assert isinstance(sync_processor, SGPSyncTracingProcessor)
    assert isinstance(async_processor, SGPAsyncTracingProcessor)


def test_set_processor_configs_registers_every_config_without_deadlocking():
    p1, p2, p3, p4 = _patched_sgp()
    manager = TracingProcessorManager()
    done = threading.Event()

    def register():
        with p1, p2, p3, p4:
            manager.set_processor_configs([_sgp_config(), _sgp_config()])
        done.set()

    threading.Thread(target=register, daemon=True).start()

    assert done.wait(timeout=5), "set_processor_configs hung: the manager lock must be reentrant"
    assert len(manager.get_sync_processors()) == 2
    assert len(manager.get_async_processors()) == 2
