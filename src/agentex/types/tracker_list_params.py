# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

__all__ = ["TrackerListParams"]


class TrackerListParams(TypedDict, total=False):
    agent_id: Optional[str]
    """Agent ID"""

    limit: int
    """Limit"""

    page_number: int
    """Page number"""

    task_id: Optional[str]
    """Task ID"""
