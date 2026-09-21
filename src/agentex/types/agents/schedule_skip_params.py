# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["ScheduleSkipParams"]


class ScheduleSkipParams(TypedDict, total=False):
    agent_id: Required[str]

    scheduled_time: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]
    """Specific scheduled fire time to skip."""
