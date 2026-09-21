# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypedDict

from ..._utils import PropertyInfo
from ..message_author import MessageAuthor

__all__ = ["ScheduleUpdateByNameParams", "InitialInput"]


class ScheduleUpdateByNameParams(TypedDict, total=False):
    agent_id: Required[str]

    cron_expression: Optional[str]
    """New cron cadence. Mutually exclusive with interval_seconds."""

    description: Optional[str]
    """Optional description of what this schedule does."""

    end_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """When the schedule should stop being active."""

    initial_input: Optional[InitialInput]
    """The first input delivered to each freshly created scheduled task."""

    interval_seconds: Optional[int]
    """New interval cadence in seconds. Mutually exclusive with cron_expression."""

    body_name: Annotated[Optional[str], PropertyInfo(alias="name")]
    """Human-readable name, unique among active schedules for the agent."""

    paused: Optional[bool]
    """Pause/resume the schedule as part of the update."""

    start_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """When the schedule should start being active."""

    task_metadata: Optional[Dict[str, object]]
    """Metadata copied onto each created task at fire time."""

    task_params: Optional[Dict[str, object]]
    """Resolved config forwarded as task `params` at fire time."""

    timezone: Optional[str]
    """IANA timezone the cron expression is evaluated in."""


class InitialInput(TypedDict, total=False):
    """The first input delivered to each freshly created scheduled task."""

    content: Required[str]
    """The initial prompt delivered to the task."""

    author: MessageAuthor
    """The author attributed to the initial input."""

    type: Literal["text"]
    """Input content type."""
