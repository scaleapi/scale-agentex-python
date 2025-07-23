# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Union, Optional
from typing_extensions import Literal, Annotated, TypeAlias

from .task import Task
from .event import Event
from .._utils import PropertyInfo
from .._models import BaseModel
from .data_content import DataContent
from .task_message import TaskMessage
from .text_content import TextContent
from .tool_request_content import ToolRequestContent
from .tool_response_content import ToolResponseContent

__all__ = [
    "AgentRpcByNameResponse",
    "Result",
    "ResultStreamTaskMessageStart",
    "ResultStreamTaskMessageStartContent",
    "ResultStreamTaskMessageDelta",
    "ResultStreamTaskMessageDeltaDelta",
    "ResultStreamTaskMessageDeltaDeltaTextDelta",
    "ResultStreamTaskMessageDeltaDeltaDataDelta",
    "ResultStreamTaskMessageDeltaDeltaToolRequestDelta",
    "ResultStreamTaskMessageDeltaDeltaToolResponseDelta",
    "ResultStreamTaskMessageFull",
    "ResultStreamTaskMessageFullContent",
    "ResultStreamTaskMessageDone",
]

ResultStreamTaskMessageStartContent: TypeAlias = Annotated[
    Union[TextContent, DataContent, ToolRequestContent, ToolResponseContent], PropertyInfo(discriminator="type")
]


class ResultStreamTaskMessageStart(BaseModel):
    content: ResultStreamTaskMessageStartContent

    index: Optional[int] = None

    parent_task_message: Optional[TaskMessage] = None
    """Represents a message in the agent system.

    This entity is used to store messages in MongoDB, with each message associated
    with a specific task.
    """

    type: Optional[Literal["start"]] = None


class ResultStreamTaskMessageDeltaDeltaTextDelta(BaseModel):
    text_delta: Optional[str] = None

    type: Optional[Literal["text"]] = None


class ResultStreamTaskMessageDeltaDeltaDataDelta(BaseModel):
    data_delta: Optional[str] = None

    type: Optional[Literal["data"]] = None


class ResultStreamTaskMessageDeltaDeltaToolRequestDelta(BaseModel):
    name: str

    tool_call_id: str

    arguments_delta: Optional[str] = None

    type: Optional[Literal["tool_request"]] = None


class ResultStreamTaskMessageDeltaDeltaToolResponseDelta(BaseModel):
    name: str

    tool_call_id: str

    content_delta: Optional[str] = None

    type: Optional[Literal["tool_response"]] = None


ResultStreamTaskMessageDeltaDelta: TypeAlias = Annotated[
    Union[
        ResultStreamTaskMessageDeltaDeltaTextDelta,
        ResultStreamTaskMessageDeltaDeltaDataDelta,
        ResultStreamTaskMessageDeltaDeltaToolRequestDelta,
        ResultStreamTaskMessageDeltaDeltaToolResponseDelta,
        None,
    ],
    PropertyInfo(discriminator="type"),
]


class ResultStreamTaskMessageDelta(BaseModel):
    delta: Optional[ResultStreamTaskMessageDeltaDelta] = None
    """Delta for text updates"""

    index: Optional[int] = None

    parent_task_message: Optional[TaskMessage] = None
    """Represents a message in the agent system.

    This entity is used to store messages in MongoDB, with each message associated
    with a specific task.
    """

    type: Optional[Literal["delta"]] = None


ResultStreamTaskMessageFullContent: TypeAlias = Annotated[
    Union[TextContent, DataContent, ToolRequestContent, ToolResponseContent], PropertyInfo(discriminator="type")
]


class ResultStreamTaskMessageFull(BaseModel):
    content: ResultStreamTaskMessageFullContent

    index: Optional[int] = None

    parent_task_message: Optional[TaskMessage] = None
    """Represents a message in the agent system.

    This entity is used to store messages in MongoDB, with each message associated
    with a specific task.
    """

    type: Optional[Literal["full"]] = None


class ResultStreamTaskMessageDone(BaseModel):
    index: Optional[int] = None

    parent_task_message: Optional[TaskMessage] = None
    """Represents a message in the agent system.

    This entity is used to store messages in MongoDB, with each message associated
    with a specific task.
    """

    type: Optional[Literal["done"]] = None


Result: TypeAlias = Union[
    List[TaskMessage],
    ResultStreamTaskMessageStart,
    ResultStreamTaskMessageDelta,
    ResultStreamTaskMessageFull,
    ResultStreamTaskMessageDone,
    Task,
    Event,
    None,
]


class AgentRpcByNameResponse(BaseModel):
    result: Optional[Result] = None
    """The result of the agent RPC request"""

    id: Union[int, str, None] = None

    error: Optional[object] = None

    jsonrpc: Optional[Literal["2.0"]] = None
