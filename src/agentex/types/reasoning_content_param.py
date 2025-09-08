# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal, Required, TypedDict

from .._types import SequenceNotStr
from .message_style import MessageStyle
from .message_author import MessageAuthor

__all__ = ["ReasoningContentParam"]


class ReasoningContentParam(TypedDict, total=False):
    author: Required[MessageAuthor]
    """
    The role of the messages author, in this case `system`, `user`, `assistant`, or
    `tool`.
    """

    summary: Required[SequenceNotStr[str]]
    """A list of short reasoning summaries"""

    content: Optional[SequenceNotStr[str]]
    """The reasoning content or chain-of-thought text"""

    style: MessageStyle
    """The style of the message.

    This is used by the client to determine how to display the message.
    """

    type: Literal["reasoning"]
    """The type of the message, in this case `reasoning`."""
