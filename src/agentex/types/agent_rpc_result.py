# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Union, Optional
from typing_extensions import Literal, TypeAlias

from .task import Task
from .event import Event
from .._models import BaseModel
from .task_message import TaskMessage
from .task_message_delta import TaskMessageDelta
from .task_message_content import TaskMessageContent

__all__ = [
    "AgentRpcResult",
    "StreamTaskMessageStart",
    "StreamTaskMessageDelta",
    "StreamTaskMessageFull",
    "StreamTaskMessageDone",
]


class StreamTaskMessageStart(BaseModel):
    content: TaskMessageContent

    index: Optional[int] = None

    parent_task_message: Optional[TaskMessage] = None
    """Represents a message in the agent system.

    This entity is used to store messages in MongoDB, with each message associated
    with a specific task.
    """

    type: Optional[Literal["start"]] = None


class StreamTaskMessageDelta(BaseModel):
    delta: Optional[TaskMessageDelta] = None
    """Delta for text updates"""

    index: Optional[int] = None

    parent_task_message: Optional[TaskMessage] = None
    """Represents a message in the agent system.

    This entity is used to store messages in MongoDB, with each message associated
    with a specific task.
    """

    type: Optional[Literal["delta"]] = None


class StreamTaskMessageFull(BaseModel):
    content: TaskMessageContent

    index: Optional[int] = None

    parent_task_message: Optional[TaskMessage] = None
    """Represents a message in the agent system.

    This entity is used to store messages in MongoDB, with each message associated
    with a specific task.
    """

    type: Optional[Literal["full"]] = None


class StreamTaskMessageDone(BaseModel):
    index: Optional[int] = None

    parent_task_message: Optional[TaskMessage] = None
    """Represents a message in the agent system.

    This entity is used to store messages in MongoDB, with each message associated
    with a specific task.
    """

    type: Optional[Literal["done"]] = None


AgentRpcResult: TypeAlias = Union[
    List[TaskMessage],
    StreamTaskMessageStart,
    StreamTaskMessageDelta,
    StreamTaskMessageFull,
    StreamTaskMessageDone,
    Task,
    Event,
    None,
]
