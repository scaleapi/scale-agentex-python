from __future__ import annotations

from datetime import datetime

from temporalio import activity, workflow


def in_temporal_workflow():
    try:
        return workflow.in_workflow()
    except RuntimeError:
        return False


def heartbeat_if_in_workflow(heartbeat_name: str):
    if in_temporal_workflow():
        activity.heartbeat(heartbeat_name)


def workflow_now_if_in_workflow() -> datetime | None:
    # Returns Temporal's deterministic workflow clock when called from inside a
    # workflow, otherwise None. Used to stamp messages with a monotonic
    # `created_at` so two awaited messages.create calls from the same workflow
    # cannot collide at the server. Outside a workflow (sync agents, plain
    # async activities) the server's wall clock is fine.
    if in_temporal_workflow():
        return workflow.now()
    return None
