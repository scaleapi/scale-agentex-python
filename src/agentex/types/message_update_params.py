# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Literal, Required, TypedDict

from .task_message_content_param import TaskMessageContentParam

__all__ = ["MessageUpdateParams"]


class MessageUpdateParams(TypedDict, total=False):
    content: Required[TaskMessageContentParam]

    task_id: Required[str]

    streaming_status: Optional[Literal["IN_PROGRESS", "DONE"]]
