# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Optional
from typing_extensions import TypeAlias, TypedDict

from .data_content_param import DataContentParam
from .text_content_param import TextContentParam
from .tool_request_content_param import ToolRequestContentParam
from .tool_response_content_param import ToolResponseContentParam

__all__ = ["SendEventRequestParam", "Content"]

Content: TypeAlias = Union[TextContentParam, DataContentParam, ToolRequestContentParam, ToolResponseContentParam]


class SendEventRequestParam(TypedDict, total=False):
    content: Optional[Content]
    """The content to send to the event"""

    task_id: Optional[str]
    """The ID of the task that the event was sent to"""

    task_name: Optional[str]
    """The name of the task that the event was sent to"""
