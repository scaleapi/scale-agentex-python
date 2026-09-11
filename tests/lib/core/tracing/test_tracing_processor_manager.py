from types import SimpleNamespace

import pytest

from agentex.lib.core.tracing.tracing_processor_manager import TracingProcessorManager


def test_unknown_processor_type_is_rejected_by_name():
    manager = TracingProcessorManager()

    with pytest.raises(ValueError, match="agentex.*sgp"):
        manager.add_processor_config(SimpleNamespace(type="agentex"))  # type: ignore[arg-type]

    assert manager.get_sync_processors() == []
    assert manager.get_async_processors() == []
