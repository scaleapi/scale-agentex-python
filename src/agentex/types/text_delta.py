# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["TextDelta"]


class TextDelta(BaseModel):
    text_delta: Optional[str] = None

    type: Optional[Literal["text"]] = None
