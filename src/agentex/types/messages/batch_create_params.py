# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable
from typing_extensions import Required, TypedDict

from ..task_message_content_param import TaskMessageContentParam

__all__ = ["BatchCreateParams"]


class BatchCreateParams(TypedDict, total=False):
    contents: Required[Iterable[TaskMessageContentParam]]

    task_id: Required[str]
