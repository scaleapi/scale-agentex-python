# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Optional
from typing_extensions import Literal, Required, TypeAlias, TypedDict

from .data_content_param import DataContentParam
from .text_content_param import TextContentParam
from .tool_request_content_param import ToolRequestContentParam
from .tool_response_content_param import ToolResponseContentParam

__all__ = ["MessageCreateParams", "Content"]


class MessageCreateParams(TypedDict, total=False):
    content: Required[Content]

    task_id: Required[str]

    streaming_status: Optional[Literal["IN_PROGRESS", "DONE"]]


Content: TypeAlias = Union[TextContentParam, DataContentParam, ToolRequestContentParam, ToolResponseContentParam]
