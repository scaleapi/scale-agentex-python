# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal, Required, TypedDict

from .message_style import MessageStyle
from .message_author import MessageAuthor

__all__ = ["ToolResponseContentParam"]


class ToolResponseContentParam(TypedDict, total=False):
    author: Required[MessageAuthor]
    """
    The role of the messages author, in this case `system`, `user`, `assistant`, or
    `tool`.
    """

    content: Required[object]
    """The result of the tool."""

    name: Required[str]
    """The name of the tool that is being responded to."""

    tool_call_id: Required[str]
    """The ID of the tool call that is being responded to."""

    style: MessageStyle
    """The style of the message.

    This is used by the client to determine how to display the message.
    """

    type: Literal["tool_response"]
    """The type of the message, in this case `tool_response`."""
