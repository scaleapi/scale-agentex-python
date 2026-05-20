# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from datetime import datetime
from typing_extensions import Literal

from ..._models import BaseModel

__all__ = ["ScheduleListResponse", "Schedule"]


class Schedule(BaseModel):
    """Abbreviated schedule info for list responses"""

    agent_id: str
    """ID of the agent this schedule belongs to"""

    name: str
    """Human-readable name for the schedule"""

    schedule_id: str
    """Unique identifier for the schedule"""

    state: Literal["ACTIVE", "PAUSED"]
    """Current state of the schedule"""

    next_action_time: Optional[datetime] = None
    """Next scheduled execution time"""

    workflow_name: Optional[str] = None
    """Name of the scheduled workflow"""


class ScheduleListResponse(BaseModel):
    """Response model for listing schedules"""

    schedules: List[Schedule]
    """List of schedules"""

    total: int
    """Total number of schedules"""
