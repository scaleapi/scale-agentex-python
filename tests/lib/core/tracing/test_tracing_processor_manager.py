from __future__ import annotations

import threading
from typing import Any, cast
from dataclasses import dataclass

from agentex.lib.core.tracing.tracing_processor_manager import TracingProcessorManager


@dataclass
class _FakeConfig:
    type: str = "fake"


class _FakeProcessor:
    def __init__(self, config: Any) -> None:
        self.config = config


def _manager() -> TracingProcessorManager:
    manager = TracingProcessorManager()
    manager.sync_config_registry["fake"] = cast(Any, _FakeProcessor)
    manager.async_config_registry["fake"] = cast(Any, _FakeProcessor)
    return manager


def _finishes(target: Any, timeout: float = 5.0) -> bool:
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    return not thread.is_alive()


def test_set_processor_configs_registers_every_config_without_deadlocking() -> None:
    manager = _manager()
    configs = [_FakeConfig(), _FakeConfig()]

    finished = _finishes(lambda: manager.set_processor_configs(cast(Any, configs)))

    assert finished, "set_processor_configs blocked on the manager's own lock"
    assert [cast(Any, p).config for p in manager.get_sync_processors()] == configs
    assert [cast(Any, p).config for p in manager.get_async_processors()] == configs


def test_add_processor_config_still_registers_one_pair() -> None:
    manager = _manager()

    manager.add_processor_config(cast(Any, _FakeConfig()))

    assert len(manager.get_sync_processors()) == 1
    assert len(manager.get_async_processors()) == 1
