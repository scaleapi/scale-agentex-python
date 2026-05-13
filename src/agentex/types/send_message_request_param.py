# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Required, TypedDict

from .task_message_content_param import TaskMessageContentParam

__all__ = ["SendMessageRequestParam"]


class SendMessageRequestParam(TypedDict, total=False):
    content: Required[TaskMessageContentParam]
    """The message that was sent to the agent"""

    stream: bool
    """Whether to stream the response message back to the client"""

    task_id: Optional[str]
    """The ID of the task that the message was sent to"""

    task_name: Optional[str]
    """The name of the task that the message was sent to"""

    task_params: Optional[Dict[str, object]]
    """The parameters for the task (only used when creating new tasks)"""
