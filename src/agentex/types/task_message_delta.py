# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Union
from typing_extensions import Annotated, TypeAlias

from .._utils import PropertyInfo
from .data_delta import DataDelta
from .text_delta import TextDelta
from .tool_request_delta import ToolRequestDelta
from .tool_response_delta import ToolResponseDelta
from .reasoning_content_delta import ReasoningContentDelta
from .reasoning_summary_delta import ReasoningSummaryDelta

__all__ = ["TaskMessageDelta"]

TaskMessageDelta: TypeAlias = Annotated[
    Union[TextDelta, DataDelta, ToolRequestDelta, ToolResponseDelta, ReasoningSummaryDelta, ReasoningContentDelta],
    PropertyInfo(discriminator="type"),
]
