# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Optional
from typing_extensions import Literal, TypedDict

__all__ = ["TaskListParams"]


class TaskListParams(TypedDict, total=False):
    agent_id: Optional[str]

    agent_name: Optional[str]

    limit: int

    page_number: int

    relationships: List[Literal["agents"]]
