# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["AgentTaskTracker"]


class AgentTaskTracker(BaseModel):
    id: str
    """The UUID of the agent task tracker"""

    agent_id: str
    """The UUID of the agent"""

    created_at: datetime
    """When the agent task tracker was created"""

    task_id: str
    """The UUID of the task"""

    last_processed_event_id: Optional[str] = None
    """The last processed event ID"""

    status: Optional[str] = None
    """Processing status"""

    status_reason: Optional[str] = None
    """Optional status reason"""

    updated_at: Optional[datetime] = None
    """When the agent task tracker was last updated"""
