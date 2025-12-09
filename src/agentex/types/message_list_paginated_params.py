# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal, Required, TypedDict

__all__ = ["MessageListPaginatedParams"]


class MessageListPaginatedParams(TypedDict, total=False):
    task_id: Required[str]
    """The task ID"""

    cursor: Optional[str]

    direction: Literal["older", "newer"]

    limit: int
