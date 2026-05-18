# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from datetime import datetime
from typing_extensions import Literal

from ..._models import BaseModel

__all__ = ["ScheduleTriggerResponse", "Action", "Spec"]


class Action(BaseModel):
    """Information about the scheduled action"""

    task_queue: str
    """Task queue for the workflow"""

    workflow_id_prefix: str
    """Prefix for workflow execution IDs"""

    workflow_name: str
    """Name of the workflow being executed"""

    workflow_params: Optional[List[object]] = None
    """Parameters passed to the workflow"""


class Spec(BaseModel):
    """Schedule specification"""

    cron_expressions: Optional[List[str]] = None
    """Cron expressions for the schedule"""

    end_at: Optional[datetime] = None
    """When the schedule stops being active"""

    intervals_seconds: Optional[List[int]] = None
    """Interval specifications in seconds"""

    start_at: Optional[datetime] = None
    """When the schedule starts being active"""


class ScheduleTriggerResponse(BaseModel):
    """Response model for schedule operations"""

    action: Action
    """Information about the scheduled action"""

    agent_id: str
    """ID of the agent this schedule belongs to"""

    name: str
    """Human-readable name for the schedule"""

    schedule_id: str
    """Unique identifier for the schedule"""

    spec: Spec
    """Schedule specification"""

    state: Literal["ACTIVE", "PAUSED"]
    """Current state of the schedule"""

    created_at: Optional[datetime] = None
    """When the schedule was created"""

    last_action_time: Optional[datetime] = None
    """When the schedule last executed"""

    next_action_times: Optional[List[datetime]] = None
    """Upcoming scheduled execution times"""

    num_actions_missed: Optional[int] = None
    """Number of scheduled executions that were missed"""

    num_actions_taken: Optional[int] = None
    """Number of times the schedule has executed"""
