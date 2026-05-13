# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Iterable
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo
from ..task_message_content_param import TaskMessageContentParam

__all__ = ["BatchCreateParams"]


class BatchCreateParams(TypedDict, total=False):
    contents: Required[Iterable[TaskMessageContentParam]]

    task_id: Required[str]

    created_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """Optional base timestamp.

    Each message in the batch is stamped with base + i milliseconds to guarantee
    unique, monotonic ordering. If omitted, the server stamps datetime.now(UTC) at
    insert time.
    """
