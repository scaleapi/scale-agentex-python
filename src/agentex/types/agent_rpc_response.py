# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.
from __future__ import annotations

from typing import Union, Optional
from typing_extensions import Literal

from .task import Task
from .event import Event
from .._models import BaseModel
from .task_message import TaskMessage
from .agent_rpc_result import AgentRpcResult
from .task_message_update import TaskMessageUpdate

__all__ = ["AgentRpcResponse"]


class BaseAgentRpcResponse(BaseModel):
    id: Union[int, str, None] = None
    error: Optional[object] = None
    jsonrpc: Optional[Literal["2.0"]] = None


class AgentRpcResponse(BaseAgentRpcResponse):
    result: Optional[AgentRpcResult] = None
    """The result of the agent RPC request"""


class CreateTaskResponse(BaseAgentRpcResponse):
    result: Task
    """The result of the task creation"""


class CancelTaskResponse(BaseAgentRpcResponse):
    result: Task
    """The result of the task cancellation"""


class SendMessageResponse(BaseAgentRpcResponse):
    result: list[TaskMessage]
    """The result of the message sending"""

class SendMessageStreamResponse(BaseAgentRpcResponse):
    result: TaskMessageUpdate
    """The result of the message sending"""


class SendEventResponse(BaseAgentRpcResponse):
    result: Event
    """The result of the event sending"""