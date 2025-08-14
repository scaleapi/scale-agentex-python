# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union, Optional
from typing_extensions import Literal, Required, TypeAlias, TypedDict

from .message_style import MessageStyle
from .message_author import MessageAuthor
from .data_content_param import DataContentParam
from .text_content_param import TextContentParam
from .tool_request_content_param import ToolRequestContentParam
from .tool_response_content_param import ToolResponseContentParam

__all__ = ["TaskMessageContentParam", "ReasoningContent"]


class ReasoningContent(TypedDict, total=False):
    author: Required[MessageAuthor]
    """
    The role of the messages author, in this case `system`, `user`, `assistant`, or
    `tool`.
    """

    summary: Required[List[str]]
    """A list of short reasoning summaries"""

    content: Optional[List[str]]
    """The reasoning content or chain-of-thought text"""

    style: MessageStyle
    """The style of the message.

    This is used by the client to determine how to display the message.
    """

    type: Literal["reasoning"]
    """The type of the message, in this case `reasoning`."""


TaskMessageContentParam: TypeAlias = Union[
    TextContentParam, ReasoningContent, DataContentParam, ToolRequestContentParam, ToolResponseContentParam
]
