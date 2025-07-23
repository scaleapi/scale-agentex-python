# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from typing_extensions import Required, TypeAlias, TypedDict

from .task_message_content_param import TaskMessageContentParam

__all__ = ["AgentRpcParams", "CreateTaskRequest", "CancelTaskRequest", "SendMessageRequest", "SendEventRequest"]


class CreateTaskRequest(TypedDict, total=False):
    name: Optional[str]
    """The name of the task to create"""

    params: Optional[Dict[str, object]]
    """The parameters for the task"""


class CancelTaskRequest(TypedDict, total=False):
    task_id: Optional[str]
    """The ID of the task to cancel. Either this or task_name must be provided."""

    task_name: Optional[str]
    """The name of the task to cancel. Either this or task_id must be provided."""


class SendMessageRequest(TypedDict, total=False):
    content: Required[TaskMessageContentParam]
    """The message that was sent to the agent"""

    stream: bool
    """Whether to stream the response message back to the client"""

    task_id: Optional[str]
    """The ID of the task that the message was sent to"""


class SendEventRequest(TypedDict, total=False):
    content: Optional[TaskMessageContentParam]
    """The content to send to the event"""

    task_id: Optional[str]
    """The ID of the task that the event was sent to"""

    task_name: Optional[str]
    """The name of the task that the event was sent to"""


AgentRpcParams: TypeAlias = Union[CreateTaskRequest, CancelTaskRequest, SendMessageRequest, SendEventRequest]
