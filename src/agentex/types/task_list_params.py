# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Optional
from typing_extensions import Literal, TypedDict

__all__ = ["TaskListParams"]


class TaskListParams(TypedDict, total=False):
    agent_id: Optional[str]

    agent_name: Optional[str]

    limit: int

    order_by: Optional[str]

    order_direction: str

    page_number: int

    relationships: List[Literal["agents"]]

    status: Optional[
        Literal["CANCELED", "COMPLETED", "FAILED", "RUNNING", "INTERRUPTED", "TERMINATED", "TIMED_OUT", "DELETED"]
    ]
    """Filter tasks by status (e.g. RUNNING, COMPLETED)."""

    task_metadata: Optional[str]
    """JSON-encoded object used to filter tasks via JSONB containment.

    Example: {"created_by_user_id": "abc-123"}.
    """
