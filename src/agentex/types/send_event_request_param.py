# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

from .task_message_content_param import TaskMessageContentParam

__all__ = ["SendEventRequestParam"]


class SendEventRequestParam(TypedDict, total=False):
    content: Optional[TaskMessageContentParam]
    """The content to send to the event"""

    task_id: Optional[str]
    """The ID of the task that the event was sent to"""

    task_name: Optional[str]
    """The name of the task that the event was sent to"""
