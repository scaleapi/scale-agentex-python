# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

__all__ = ["StateListParams"]


class StateListParams(TypedDict, total=False):
    agent_id: Optional[str]
    """Agent ID"""

    limit: int
    """Limit"""

    order_by: Optional[str]
    """Field to order by"""

    order_direction: str
    """Order direction (asc or desc)"""

    page_number: int
    """Page number"""

    task_id: Optional[str]
    """Task ID"""
