# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["ToolRequestDelta"]


class ToolRequestDelta(BaseModel):
    name: str

    tool_call_id: str

    arguments_delta: Optional[str] = None

    type: Optional[Literal["tool_request"]] = None
