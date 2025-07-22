# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from typing_extensions import Literal

from .._models import BaseModel
from .message_style import MessageStyle
from .message_author import MessageAuthor

__all__ = ["TextContent", "Attachment"]


class Attachment(BaseModel):
    file_id: str
    """The unique ID of the attached file"""

    name: str
    """The name of the file"""

    size: int
    """The size of the file in bytes"""

    type: str
    """The MIME type or content type of the file"""


class TextContent(BaseModel):
    author: MessageAuthor
    """
    The role of the messages author, in this case `system`, `user`, `assistant`, or
    `tool`.
    """

    content: str
    """The contents of the text message."""

    attachments: Optional[List[Attachment]] = None
    """Optional list of file attachments with structured metadata."""

    format: Literal["markdown", "plain", "code"] = "plain"
    """The format of the message.

    This is used by the client to determine how to display the message.
    """

    style: MessageStyle = "static"
    """The style of the message.

    This is used by the client to determine how to display the message.
    """

    type: Literal["text"] = "text"
    """The type of the message, in this case `text`."""
