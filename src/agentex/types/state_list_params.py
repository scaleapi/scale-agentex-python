# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

__all__ = ["StateListParams"]


class StateListParams(TypedDict, total=False):
    agent_id: Optional[str]
    """Agent ID"""

    task_id: Optional[str]
    """Task ID"""
