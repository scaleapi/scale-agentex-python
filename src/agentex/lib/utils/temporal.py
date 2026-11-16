from __future__ import annotations

from datetime import datetime

from temporalio import activity, workflow


def in_temporal_workflow():
    try:
        return workflow.in_workflow()
    except RuntimeError:
        return False


def heartbeat_if_in_activity(heartbeat_name: str) -> None:
    """Records a Temporal activity heartbeat when called from inside an activity.

    ``activity.heartbeat`` is only legal inside an activity, so this stays a
    silent no-op everywhere else: workflow code and sync agents reach the same
    shared services and must not raise there.
    """
    if activity.in_activity():
        activity.heartbeat(heartbeat_name)


def heartbeat_if_in_workflow(heartbeat_name: str) -> None:
    """Deprecated alias for :func:`heartbeat_if_in_activity`.

    Kept so the existing call sites keep working; prefer the activity-named
    helper in new code.
    """
    heartbeat_if_in_activity(heartbeat_name)


def workflow_now_if_in_workflow() -> datetime | None:
    # Returns Temporal's deterministic workflow clock when called from inside a
    # workflow, otherwise None. Used to stamp messages with a monotonic
    # `created_at` so two awaited messages.create calls from the same workflow
    # cannot collide at the server. Outside a workflow (sync agents, plain
    # async activities) the server's wall clock is fine.
    if in_temporal_workflow():
        return workflow.now()
    return None
