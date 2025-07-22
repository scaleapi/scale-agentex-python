# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["DataDelta"]


class DataDelta(BaseModel):
    data_delta: Optional[str] = None

    type: Optional[Literal["data"]] = None
