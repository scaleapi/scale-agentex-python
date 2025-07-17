# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Union, Optional
from datetime import datetime
from typing_extensions import Annotated, TypeAlias

from .._utils import PropertyInfo
from .._models import BaseModel
from .data_content import DataContent
from .text_content import TextContent
from .tool_request_content import ToolRequestContent
from .tool_response_content import ToolResponseContent

__all__ = ["Event", "Content"]

Content: TypeAlias = Annotated[
    Union[TextContent, DataContent, ToolRequestContent, ToolResponseContent, None], PropertyInfo(discriminator="type")
]


class Event(BaseModel):
    id: str
    """The UUID of the event"""

    agent_id: str
    """The UUID of the agent that the event belongs to"""

    sequence_id: int
    """The sequence ID of the event"""

    task_id: str
    """The UUID of the task that the event belongs to"""

    content: Optional[Content] = None
    """The content of the event"""

    created_at: Optional[datetime] = None
    """The timestamp of the event"""
