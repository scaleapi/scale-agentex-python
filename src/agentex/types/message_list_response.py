# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel
from .task_message import TaskMessage

__all__ = ["MessageListResponse", "PaginatedMessagesResponse"]


# Original response type: list of messages
MessageListResponse = List[TaskMessage]


class PaginatedMessagesResponse(BaseModel):
    """Response with cursor pagination metadata."""

    data: List[TaskMessage]
    """List of messages"""

    next_cursor: Optional[str] = None
    """Cursor for fetching the next page of older messages.
    Pass this as the `cursor` parameter in the next request.
    None if there are no more messages."""

    has_more: bool = False
    """Whether there are more messages to fetch"""
