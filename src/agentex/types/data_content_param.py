# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict
from typing_extensions import Literal, Required, TypedDict

from .message_style import MessageStyle
from .message_author import MessageAuthor

__all__ = ["DataContentParam"]


class DataContentParam(TypedDict, total=False):
    author: Required[MessageAuthor]
    """
    The role of the messages author, in this case `system`, `user`, `assistant`, or
    `tool`.
    """

    data: Required[Dict[str, object]]
    """The contents of the data message."""

    style: MessageStyle
    """The style of the message.

    This is used by the client to determine how to display the message.
    """

    type: Literal["data"]
    """The type of the message, in this case `data`."""
