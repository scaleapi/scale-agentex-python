from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from agentex.types.task_message import TaskMessage
from agentex.types.task_message_content import TaskMessageContent
from agentex.lib.utils.model_utils import BaseModel


class BaseTaskMessageDelta(BaseModel):
    """
    Base class for all delta updates

    Attributes:
        type: The type of delta update
    """

    type: Literal["text", "data", "tool_request", "tool_response"]


class TextDelta(BaseTaskMessageDelta):
    """
    Delta for text updates

    Attributes:
        type: The type of delta update
        text_delta: The delta for the text
    """

    type: Literal["text"] = "text"
    text_delta: str | None = ""


class DataDelta(BaseTaskMessageDelta):
    """
    Delta for data updates

    Attributes:
        type: The type of delta update
        data_delta: The delta for the data
    """

    type: Literal["data"] = "data"
    data_delta: str | None = ""


class ToolRequestDelta(BaseTaskMessageDelta):
    """
    Delta for tool request updates

    Attributes:
        type: The type of delta update
        name: The name of the tool
        arguments_delta: The delta for the arguments
    """

    type: Literal["tool_request"] = "tool_request"
    tool_call_id: str
    name: str
    arguments_delta: str | None = ""


class ToolResponseDelta(BaseTaskMessageDelta):
    """
    Delta for tool response updates

    Attributes:
        type: The type of delta update
        tool_response_delta: The delta for the tool response
    """

    type: Literal["tool_response"] = "tool_response"
    tool_call_id: str
    name: str
    tool_response_delta: str | None = ""


TaskMessageDelta = Annotated[
    TextDelta | DataDelta | ToolRequestDelta | ToolResponseDelta,
    Field(discriminator="type"),
]


class StreamTaskMessage(BaseModel):
    """Base class for all task message stream events

    Attributes:
        type: The type of task message update
        parent_task_message: The parent task message
        index: The index of the task message
    """

    type: Literal["start", "delta", "full", "done"]
    # Used for streaming chunks to a direct parent_task_message
    parent_task_message: TaskMessage | None = None
    # Used to correlate chunks of different task messages with each other
    # directly in the Sync ACP case
    index: int | None = None

    @model_validator(mode="after")
    def validate_message_correlation(self):
        """Ensure exactly one of index or parent_task_message is set"""
        has_parent = self.parent_task_message is not None
        has_index = self.index is not None

        if not has_parent and not has_index:
            raise ValueError("Either 'index' or 'parent_task_message' must be set")

        if has_parent and has_index:
            raise ValueError(
                "Cannot set both 'index' and 'parent_task_message' - only one is allowed"
            )

        return self


# Everything is streamed as a partial json blob, except for text.
class StreamTaskMessageStart(StreamTaskMessage):
    """Event for starting a streaming message

    Attributes:
        type: The type of task message update
        content: The content of the task message
    """

    type: Literal["start"] = "start"
    content: TaskMessageContent


class StreamTaskMessageDelta(StreamTaskMessage):
    """Event for streaming chunks of content

    Attributes:
        type: The type of task message update
        delta: The delta of the task message
    """

    type: Literal["delta"] = "delta"
    delta: TaskMessageDelta | None = None


class StreamTaskMessageFull(StreamTaskMessage):
    """Event for streaming the full content

    Attributes:
        type: The type of task message update
        content: The content of the task message
    """

    type: Literal["full"] = "full"
    content: TaskMessageContent


class StreamTaskMessageDone(StreamTaskMessage):
    """Event for indicating the task is done

    Attributes:
        type: The type of task message update
    """

    type: Literal["done"] = "done"


TaskMessageUpdate = Annotated[
    StreamTaskMessageStart
    | StreamTaskMessageDelta
    | StreamTaskMessageFull
    | StreamTaskMessageDone,
    Field(discriminator="type"),
]
