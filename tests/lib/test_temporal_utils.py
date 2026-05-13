"""Tests for agentex.lib.utils.temporal helpers."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from agentex.lib.utils import temporal as _temporal_mod
from agentex.lib.utils.temporal import (
    in_temporal_workflow,
    workflow_now_if_in_workflow,
)


def test_in_temporal_workflow_returns_false_outside_workflow() -> None:
    # Calling outside a workflow context raises RuntimeError internally, which
    # the helper swallows.
    assert in_temporal_workflow() is False


def test_workflow_now_if_in_workflow_returns_none_outside_workflow() -> None:
    assert workflow_now_if_in_workflow() is None


def test_workflow_now_if_in_workflow_returns_workflow_now_when_inside() -> None:
    fixed = datetime(2026, 5, 13, 18, 30, 0)
    with patch.object(_temporal_mod, "in_temporal_workflow", return_value=True), patch.object(
        _temporal_mod.workflow, "now", return_value=fixed
    ):
        assert workflow_now_if_in_workflow() == fixed
