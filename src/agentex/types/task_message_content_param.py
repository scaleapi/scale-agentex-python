# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from typing_extensions import TypeAlias

from .data_content_param import DataContentParam
from .text_content_param import TextContentParam
from .tool_request_content_param import ToolRequestContentParam
from .tool_response_content_param import ToolResponseContentParam

__all__ = ["TaskMessageContentParam"]

TaskMessageContentParam: TypeAlias = Union[
    TextContentParam, DataContentParam, ToolRequestContentParam, ToolResponseContentParam
]
