# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Optional
from typing_extensions import Required, TypeAlias, TypedDict

from .streaming_status import StreamingStatus
from .data_content_param import DataContentParam
from .text_content_param import TextContentParam
from .tool_request_content_param import ToolRequestContentParam
from .tool_response_content_param import ToolResponseContentParam

__all__ = ["MessageUpdateParams", "Content"]


class MessageUpdateParams(TypedDict, total=False):
    content: Required[Content]

    task_id: Required[str]

    streaming_status: Optional[StreamingStatus]


Content: TypeAlias = Union[TextContentParam, DataContentParam, ToolRequestContentParam, ToolResponseContentParam]
