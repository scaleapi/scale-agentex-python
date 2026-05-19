# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["ScheduleUnpauseParams"]


class ScheduleUnpauseParams(TypedDict, total=False):
    agent_id: Required[str]

    note: Optional[str]
    """Optional note explaining why the schedule was unpaused"""
