# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Union, Optional
from datetime import datetime
from typing_extensions import Literal, Annotated, TypeAlias

from .._utils import PropertyInfo
from .._models import BaseModel
from .data_content import DataContent
from .text_content import TextContent
from .tool_request_content import ToolRequestContent
from .tool_response_content import ToolResponseContent

__all__ = ["TaskMessage", "Content"]

Content: TypeAlias = Annotated[
    Union[TextContent, DataContent, ToolRequestContent, ToolResponseContent], PropertyInfo(discriminator="type")
]


class TaskMessage(BaseModel):
    content: Content
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
