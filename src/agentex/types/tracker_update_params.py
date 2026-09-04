# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

__all__ = ["TrackerUpdateParams"]


class TrackerUpdateParams(TypedDict, total=False):
    last_processed_event_id: Optional[str]
    """The most recent processed event ID (omit to leave unchanged)"""

    status: Optional[str]
    """Processing status"""

    status_reason: Optional[str]
    """Optional status reason"""
