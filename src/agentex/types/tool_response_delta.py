# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["ToolResponseDelta"]


class ToolResponseDelta(BaseModel):
    name: str

    tool_call_id: str

    content_delta: Optional[str] = None

    type: Optional[Literal["tool_response"]] = None
