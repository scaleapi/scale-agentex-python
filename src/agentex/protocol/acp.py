from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field, BaseModel

from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.types.task_message_content import TaskMessageContent


class RPCMethod(str, Enum):
    """Available JSON-RPC methods for agent communication."""

    EVENT_SEND = "event/send"
    MESSAGE_SEND = "message/send"
    TASK_CANCEL = "task/cancel"
    TASK_CREATE = "task/create"
    TASK_INTERRUPT = "task/interrupt"


class CreateTaskParams(BaseModel):
    """Parameters for task/create method.

    Attributes:
        agent: The agent that the task was sent to.
        task: The task to be created.
        params: The parameters for the task as inputted by the user.
        request: Additional request context including headers forwarded to this agent.
    """

    agent: Agent = Field(..., description="The agent that the task was sent to")
    task: Task = Field(..., description="The task to be created")
    params: dict[str, Any] | None = Field(
        None,
        description="The parameters for the task as inputted by the user",
    )
    request: dict[str, Any] | None = Field(
        default=None,
        description="Additional request context including headers forwarded to this agent",
    )


class SendMessageParams(BaseModel):
    """Parameters for message/send method.

    Attributes:
        agent: The agent that the message was sent to.
        task: The task that the message was sent to.
        content: The message that was sent to the agent.
        stream: Whether to stream the message back to the agentex server from the agent.
        request: Additional request context including headers forwarded to this agent.
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
    request: dict[str, Any] | None = Field(
        default=None,
        description="Additional request context including headers forwarded to this agent",
    )


class SendEventParams(BaseModel):
    """Parameters for event/send method.

    Attributes:
        agent: The agent that the event was sent to.
        task: The task that the message was sent to.
        event: The event that was sent to the agent.
        request: Additional request context including headers forwarded to this agent.
    """

    agent: Agent = Field(..., description="The agent that the event was sent to")
    task: Task = Field(..., description="The task that the message was sent to")
    event: Event = Field(..., description="The event that was sent to the agent")
    request: dict[str, Any] | None = Field(
        default=None,
        description="Additional request context including headers forwarded to this agent",
    )


class CancelTaskParams(BaseModel):
    """Parameters for task/cancel method.

    Attributes:
        agent: The agent that the task was sent to.
        task: The task that was cancelled.
        request: Additional request context including headers forwarded to this agent.
    """

    agent: Agent = Field(..., description="The agent that the task was sent to")
    task: Task = Field(..., description="The task that was cancelled")
    request: dict[str, Any] | None = Field(
        default=None,
        description="Additional request context including headers forwarded to this agent",
    )


class InterruptTaskParams(BaseModel):
    """Parameters for task/interrupt method.

    Non-terminal counterpart to :class:`CancelTaskParams`. The control plane
    forwards ``task/interrupt`` to the agent so it can stop the in-flight turn
    while leaving the task continuable (status ``INTERRUPTED``, not a terminal
    status). See the interrupt-and-queue design doc, sections 5-7.

    Attributes:
        agent: The agent that the task was sent to.
        task: The task that was interrupted.
        request: Additional request context including headers forwarded to this agent.
    """

    agent: Agent = Field(..., description="The agent that the task was sent to")
    task: Task = Field(..., description="The task that was interrupted")
    request: dict[str, Any] | None = Field(
        default=None,
        description="Additional request context including headers forwarded to this agent",
    )


# Methods whose handler must finish before the RPC responds.
#
# TASK_CREATE and EVENT_SEND are here because dispatching them in the background
# loses work silently. The handlers run against Temporal: TASK_CREATE starts the
# workflow, EVENT_SEND signals it. Backgrounding both means a caller that does
# task/create followed by event/send can have its signal reach Temporal before
# the workflow exists, and the signal is dropped with `workflow not found`. The
# caller cannot tell, because the background path already answered
# {"status": "processing"} and the handler's exception is only logged.
#
# Both handlers are short Temporal RPCs, and the caller applies its own timeout,
# so awaiting them costs little and makes failures visible and retryable.
RPC_SYNC_METHODS = [
    RPCMethod.MESSAGE_SEND,
    RPCMethod.TASK_CREATE,
    RPCMethod.EVENT_SEND,
]

PARAMS_MODEL_BY_METHOD: dict[RPCMethod, type[BaseModel]] = {
    RPCMethod.EVENT_SEND: SendEventParams,
    RPCMethod.TASK_CANCEL: CancelTaskParams,
    RPCMethod.MESSAGE_SEND: SendMessageParams,
    RPCMethod.TASK_CREATE: CreateTaskParams,
    RPCMethod.TASK_INTERRUPT: InterruptTaskParams,
}
