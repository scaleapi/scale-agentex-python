# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional
from typing_extensions import Literal

from .._models import BaseModel
from .message_style import MessageStyle
from .message_author import MessageAuthor

__all__ = ["ToolRequestContent"]


class ToolRequestContent(BaseModel):
    arguments: Dict[str, object]
    """The arguments to the tool."""

    author: MessageAuthor
    """
    The role of the messages author, in this case `system`, `user`, `assistant`, or
    `tool`.
    """

    name: str
    """The name of the tool that is being requested."""

    tool_call_id: str
    """The ID of the tool call that is being requested."""

    style: MessageStyle = "static"
    """The style of the message.

    This is used by the client to determine how to display the message.
    """

    type: Literal["tool_request"] = "tool_request"
    """The type of the message, in this case `tool_request`."""
