# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional
from typing_extensions import Literal

from .._models import BaseModel
from .message_style import MessageStyle
from .message_author import MessageAuthor

__all__ = ["DataContent"]


class DataContent(BaseModel):
    author: MessageAuthor
    """
    The role of the messages author, in this case `system`, `user`, `assistant`, or
    `tool`.
    """

    data: Dict[str, object]
    """The contents of the data message."""

    style: MessageStyle = "static"
    """The style of the message.

    This is used by the client to determine how to display the message.
    """

    type: Literal["data"] = "data"
    """The type of the message, in this case `data`."""
