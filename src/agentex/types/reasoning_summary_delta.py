# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["ReasoningSummaryDelta"]


class ReasoningSummaryDelta(BaseModel):
    summary_index: int

    summary_delta: Optional[str] = None

    type: Optional[Literal["reasoning_summary"]] = None
