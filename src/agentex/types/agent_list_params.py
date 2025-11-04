# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

__all__ = ["AgentListParams"]


class AgentListParams(TypedDict, total=False):
    limit: int
    """Limit"""

    page_number: int
    """Page number"""

    task_id: Optional[str]
    """Task ID"""
