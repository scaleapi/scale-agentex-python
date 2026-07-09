# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypedDict

from ..._utils import PropertyInfo
from ..message_author import MessageAuthor

__all__ = ["ScheduleCreateParams", "InitialInput"]


class ScheduleCreateParams(TypedDict, total=False):
    initial_input: Required[InitialInput]
    """The first input delivered to each created task."""

    name: Required[str]
    """Human-readable name, unique among active schedules for the agent."""

    cron_expression: Optional[str]
    """Cron expression for the cadence (e.g.

    '0 17 \\** \\** MON-FRI'). Mutually exclusive with interval_seconds.
    """

    description: Optional[str]
    """Optional description of what this schedule does."""

    end_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """When the schedule should stop being active."""

    interval_seconds: Optional[int]
    """Interval cadence in seconds. Mutually exclusive with cron_expression."""

    paused: bool
    """Whether to create the schedule in a paused state."""

    start_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """When the schedule should start being active."""

    task_metadata: Optional[Dict[str, object]]
    """Metadata copied onto each created task at fire time."""

    task_params: Optional[Dict[str, object]]
    """Resolved config forwarded as task `params` at fire time."""

    timezone: str
    """IANA timezone the cron expression is evaluated in (e.g. 'America/New_York')."""


class InitialInput(TypedDict, total=False):
    """The first input delivered to each created task."""

    content: Required[str]
    """The initial prompt delivered to the task."""

    author: MessageAuthor
    """The author attributed to the initial input."""

    type: Literal["text"]
    """Input content type."""
