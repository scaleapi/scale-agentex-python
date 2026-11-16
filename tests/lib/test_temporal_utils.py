"""Tests for agentex.lib.utils.temporal helpers."""

from __future__ import annotations

from typing import Any
from datetime import datetime
from unittest.mock import patch

from temporalio import activity
from temporalio.testing import ActivityEnvironment

from agentex.lib.utils import temporal as _temporal_mod
from agentex.lib.utils.temporal import (
    in_temporal_workflow,
    heartbeat_if_in_activity,
    heartbeat_if_in_workflow,
    workflow_now_if_in_workflow,
)


def test_in_temporal_workflow_returns_false_outside_workflow() -> None:
    # Calling outside a workflow context raises RuntimeError internally, which
    # the helper swallows.
    assert in_temporal_workflow() is False


async def test_heartbeat_if_in_activity_heartbeats_inside_activity() -> None:
    """The helper must reach Temporal's heartbeat channel from inside an activity."""
    recorded: list[tuple[Any, ...]] = []

    @activity.defn(name="heartbeating_activity")
    async def heartbeating_activity() -> None:
        heartbeat_if_in_activity("doing slow work")

    env = ActivityEnvironment()
    env.on_heartbeat = lambda *details: recorded.append(details)

    await env.run(heartbeating_activity)

    assert recorded == [("doing slow work",)]


async def test_heartbeat_if_in_workflow_alias_heartbeats_inside_activity() -> None:
    """The legacy name stays wired to the same behaviour for existing call sites."""
    recorded: list[tuple[Any, ...]] = []

    @activity.defn(name="legacy_heartbeating_activity")
    async def legacy_heartbeating_activity() -> None:
        heartbeat_if_in_workflow("doing slow work")

    env = ActivityEnvironment()
    env.on_heartbeat = lambda *details: recorded.append(details)

    await env.run(legacy_heartbeating_activity)

    assert recorded == [("doing slow work",)]


def test_heartbeat_if_in_activity_is_noop_outside_activity() -> None:
    """Sync agents and workflow code call the same helpers and must not raise there."""
    assert activity.in_activity() is False
    heartbeat_if_in_activity("doing slow work")
    heartbeat_if_in_workflow("doing slow work")


def test_workflow_now_if_in_workflow_returns_none_outside_workflow() -> None:
    assert workflow_now_if_in_workflow() is None


def test_workflow_now_if_in_workflow_returns_workflow_now_when_inside() -> None:
    fixed = datetime(2026, 5, 13, 18, 30, 0)
    with patch.object(_temporal_mod, "in_temporal_workflow", return_value=True), patch.object(
        _temporal_mod.workflow, "now", return_value=fixed
    ):
        assert workflow_now_if_in_workflow() == fixed
