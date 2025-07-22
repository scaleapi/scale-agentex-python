# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional
from typing_extensions import Literal, Required, TypedDict

from .message_style import MessageStyle
from .message_author import MessageAuthor

__all__ = ["TextContentParam", "Attachment"]


class Attachment(TypedDict, total=False):
    file_id: Required[str]
    """The unique ID of the attached file"""

    name: Required[str]
    """The name of the file"""

    size: Required[int]
    """The size of the file in bytes"""

    type: Required[str]
    """The MIME type or content type of the file"""


class TextContentParam(TypedDict, total=False):
    author: Required[MessageAuthor]
    """
    The role of the messages author, in this case `system`, `user`, `assistant`, or
    `tool`.
    """

    content: Required[str]
    """The contents of the text message."""

    attachments: Optional[Iterable[Attachment]]
    """Optional list of file attachments with structured metadata."""

    format: Literal["markdown", "plain", "code"]
    """The format of the message.

    This is used by the client to determine how to display the message.
    """

    style: MessageStyle
    """The style of the message.

    This is used by the client to determine how to display the message.
    """

    type: Literal["text"]
    """The type of the message, in this case `text`."""
