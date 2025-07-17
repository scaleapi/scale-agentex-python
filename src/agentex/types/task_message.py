# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Union, Optional
from datetime import datetime
from typing_extensions import Annotated, TypeAlias

from .._utils import PropertyInfo
from .._models import BaseModel
from .data_content import DataContent
from .text_content import TextContent
from .streaming_status import StreamingStatus
from .tool_request_content import ToolRequestContent
from .tool_response_content import ToolResponseContent

__all__ = ["TaskMessage", "Content"]

Content: TypeAlias = Annotated[
    Union[TextContent, DataContent, ToolRequestContent, ToolResponseContent], PropertyInfo(discriminator="type")
]


class TaskMessage(BaseModel):
    id: str
    """The task message's unique id"""

    content: Content

    created_at: datetime
    """The timestamp when the message was created"""

    task_id: str

    streaming_status: Optional[StreamingStatus] = None

    updated_at: Optional[datetime] = None
    """The timestamp when the message was last updated"""
