# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Union, Optional
from typing_extensions import Literal, Annotated, TypeAlias

from .._utils import PropertyInfo
from .._models import BaseModel
from .data_delta import DataDelta
from .text_delta import TextDelta
from .tool_request_delta import ToolRequestDelta
from .tool_response_delta import ToolResponseDelta

__all__ = ["TaskMessageDelta", "ReasoningSummaryDelta", "ReasoningContentDelta"]


class ReasoningSummaryDelta(BaseModel):
    summary_index: int

    summary_delta: Optional[str] = None

    type: Optional[Literal["reasoning_summary"]] = None


class ReasoningContentDelta(BaseModel):
    content_index: int

    content_delta: Optional[str] = None

    type: Optional[Literal["reasoning_content"]] = None


TaskMessageDelta: TypeAlias = Annotated[
    Union[TextDelta, DataDelta, ToolRequestDelta, ToolResponseDelta, ReasoningSummaryDelta, ReasoningContentDelta],
    PropertyInfo(discriminator="type"),
]
