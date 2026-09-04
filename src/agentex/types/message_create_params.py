# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Optional
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypedDict

from .._utils import PropertyInfo
from .task_message_content_param import TaskMessageContentParam

__all__ = ["MessageCreateParams"]


class MessageCreateParams(TypedDict, total=False):
    content: Required[TaskMessageContentParam]

    task_id: Required[str]

    created_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """Optional timestamp for the message.

    Workflow callers should pass workflow.now() (Temporal's deterministic monotonic
    clock) so that two awaited messages.create calls from the same workflow are
    guaranteed to have monotonic timestamps regardless of HTTP scheduling at the
    server. If omitted, the server's wall clock at insert time is used.
    """

    streaming_status: Optional[Literal["IN_PROGRESS", "DONE"]]
