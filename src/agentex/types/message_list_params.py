# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["MessageListParams", "MessageListPaginatedParams"]


class MessageListParams(TypedDict, total=False):
    task_id: Required[str]
    """The task ID"""

    limit: int
    """Maximum number of messages to return (default: 50)"""

    page_number: int
    """Page number for offset-based pagination (default: 1)"""

    order_by: str
    """Field to order by (default: created_at)"""

    order_direction: str
    """Order direction - "asc" or "desc" (default: desc)"""


class MessageListPaginatedParams(TypedDict, total=False):
    task_id: Required[str]
    """The task ID"""

    limit: int
    """Maximum number of messages to return (default: 50)"""

    cursor: str
    """Opaque cursor string for pagination. Pass the `next_cursor` from
    a previous response to get the next page."""

    direction: str
    """Pagination direction - "older" to get older messages (default),
    "newer" to get newer messages."""
