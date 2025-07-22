from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.types.task_message_content import TaskMessageContent
from agentex.types.task import Task


class RPCMethod(str, Enum):
    """Available JSON-RPC methods for agent communication."""

    EVENT_SEND = "event/send"
    MESSAGE_SEND = "message/send"
    TASK_CANCEL = "task/cancel"
    TASK_CREATE = "task/create"


class CreateTaskParams(BaseModel):
    """Parameters for task/create method.

    Attributes:
        agent: The agent that the task was sent to.
        task: The task to be created.
        params: The parameters for the task as inputted by the user.
    """

    agent: Agent = Field(..., description="The agent that the task was sent to")
    task: Task = Field(..., description="The task to be created")
    params: dict[str, Any] | None = Field(
        None,
        description="The parameters for the task as inputted by the user",
    )


class SendMessageParams(BaseModel):
    """Parameters for message/send method.

    Attributes:
        agent: The agent that the message was sent to.
        task: The task that the message was sent to.
        content: The message that was sent to the agent.
        stream: Whether to stream the message back to the agentex server from the agent.
    """

    agent: Agent = Field(..., description="The agent that the message was sent to")
    task: Task = Field(..., description="The task that the message was sent to")
    content: TaskMessageContent = Field(
        ..., description="The message that was sent to the agent"
    )
    stream: bool = Field(
        False,
        description="Whether to stream the message back to the agentex server from the agent",
    )


class SendEventParams(BaseModel):
    """Parameters for event/send method.

    Attributes:
        agent: The agent that the event was sent to.
        task: The task that the message was sent to.
        event: The event that was sent to the agent.
    """

    agent: Agent = Field(..., description="The agent that the event was sent to")
    task: Task = Field(..., description="The task that the message was sent to")
    event: Event = Field(..., description="The event that was sent to the agent")


class CancelTaskParams(BaseModel):
    """Parameters for task/cancel method.

    Attributes:
        agent: The agent that the task was sent to.
        task: The task that was cancelled.
    """

    agent: Agent = Field(..., description="The agent that the task was sent to")
    task: Task = Field(..., description="The task that was cancelled")


RPC_SYNC_METHODS = [
    RPCMethod.MESSAGE_SEND,
]

PARAMS_MODEL_BY_METHOD: dict[RPCMethod, type[BaseModel]] = {
    RPCMethod.EVENT_SEND: SendEventParams,
    RPCMethod.TASK_CANCEL: CancelTaskParams,
    RPCMethod.MESSAGE_SEND: SendMessageParams,
    RPCMethod.TASK_CREATE: CreateTaskParams,
}
