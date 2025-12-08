# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["ReasoningContentDelta"]


class ReasoningContentDelta(BaseModel):
    """Delta for reasoning content updates"""

    content_index: int

    content_delta: Optional[str] = None

    type: Optional[Literal["reasoning_content"]] = None
