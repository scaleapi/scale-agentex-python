# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel
from .task_message import TaskMessage

__all__ = ["MessageListPaginatedResponse"]


class MessageListPaginatedResponse(BaseModel):
    """Response with cursor pagination metadata."""

    data: List[TaskMessage]
    """List of messages"""

    has_more: Optional[bool] = None
    """Whether there are more messages to fetch"""

    next_cursor: Optional[str] = None
    """Cursor for fetching the next page of older messages"""
