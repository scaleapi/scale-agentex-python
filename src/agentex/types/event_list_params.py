# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["EventListParams"]


class EventListParams(TypedDict, total=False):
    agent_id: Required[str]
    """The agent ID to filter events by"""

    task_id: Required[str]
    """The task ID to filter events by"""

    last_processed_event_id: Optional[str]
    """Optional event ID to get events after this ID"""

    limit: Optional[int]
    """Optional limit on number of results"""
