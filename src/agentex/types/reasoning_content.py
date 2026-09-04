# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from typing_extensions import Literal

from .._models import BaseModel
from .message_style import MessageStyle
from .message_author import MessageAuthor

__all__ = ["ReasoningContent"]


class ReasoningContent(BaseModel):
    author: MessageAuthor
    """
    The role of the messages author, in this case `system`, `user`, `assistant`, or
    `tool`.
    """

    summary: List[str]
    """A list of short reasoning summaries"""

    content: Optional[List[str]] = None
    """The reasoning content or chain-of-thought text"""

    style: Optional[MessageStyle] = None
    """The style of the message.

    This is used by the client to determine how to display the message.
    """

    type: Optional[Literal["reasoning"]] = None
    """The type of the message, in this case `reasoning`."""
