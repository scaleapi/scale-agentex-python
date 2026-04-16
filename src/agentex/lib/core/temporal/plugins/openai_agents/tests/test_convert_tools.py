"""Unit tests for TemporalStreamingModel._convert_tools tool serialization."""

from unittest.mock import MagicMock, patch

import pytest

from agentex.lib.core.temporal.plugins.openai_agents.models import (
    temporal_streaming_model as tsm_module,
)
from agentex.lib.core.temporal.plugins.openai_agents.models.temporal_streaming_model import (
    TemporalStreamingModel,
)


@pytest.fixture
def model():
    with patch(
        "agentex.lib.core.temporal.plugins.openai_agents.models.temporal_streaming_model.create_async_agentex_client"
    ):
        return TemporalStreamingModel(model_name="gpt-4o", openai_client=MagicMock())


class _FakeShellTool:
    """Stand-in for agents.tool.ShellTool for environments where it isn't installed."""

    def __init__(self, environment):
        self.environment = environment


def test_shell_tool_local_environment(model, monkeypatch):
    """ShellTool with a local environment should serialize to a 'shell' payload."""
    monkeypatch.setattr(tsm_module, "ShellTool", _FakeShellTool)

    tool = _FakeShellTool(environment={"type": "local", "skills": ["git"]})
    response_tools, _ = model._convert_tools([tool], handoffs=[])

    assert response_tools == [{"type": "shell", "environment": {"type": "local", "skills": ["git"]}}]


def test_shell_tool_defaults_environment_when_missing(model, monkeypatch):
    """ShellTool with environment=None should fall back to {'type': 'local'}."""
    monkeypatch.setattr(tsm_module, "ShellTool", _FakeShellTool)

    tool = _FakeShellTool(environment=None)
    response_tools, _ = model._convert_tools([tool], handoffs=[])

    assert response_tools == [{"type": "shell", "environment": {"type": "local"}}]


def test_shell_tool_unavailable_falls_through(model, monkeypatch, caplog):
    """If ShellTool isn't installed, an unknown tool should log a warning and be skipped."""
    monkeypatch.setattr(tsm_module, "ShellTool", None)

    class _NotAShellTool:
        pass

    with caplog.at_level("WARNING"):
        response_tools, _ = model._convert_tools([_NotAShellTool()], handoffs=[])

    assert response_tools == []
    assert any("Unknown tool type" in rec.message for rec in caplog.records)
