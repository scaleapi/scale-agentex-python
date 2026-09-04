# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from datetime import datetime

from .._models import BaseModel
from .task_message_content import TaskMessageContent

__all__ = ["Event"]


class Event(BaseModel):
    id: str
    """The UUID of the event"""

    agent_id: str
    """The UUID of the agent that the event belongs to"""

    sequence_id: int
    """The sequence ID of the event"""

    task_id: str
    """The UUID of the task that the event belongs to"""

    content: Optional[TaskMessageContent] = None
    """The content of the event"""

    created_at: Optional[datetime] = None
    """The timestamp of the event"""
