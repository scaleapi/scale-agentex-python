# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel
from .task_message_content import TaskMessageContent

__all__ = ["TaskMessage"]


class TaskMessage(BaseModel):
    content: TaskMessageContent
    """The content of the message.

    This content is not OpenAI compatible. These are messages that are meant to be
    displayed to the user.
    """

    task_id: str
    """ID of the task this message belongs to"""

    id: Optional[str] = None
    """The task message's unique id"""

    created_at: Optional[datetime] = None
    """The timestamp when the message was created"""

    streaming_status: Optional[Literal["IN_PROGRESS", "DONE"]] = None

    updated_at: Optional[datetime] = None
    """The timestamp when the message was last updated"""
