# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict
from typing_extensions import Required, TypedDict

from ..task_message_content_param import TaskMessageContentParam

__all__ = ["BatchUpdateParams"]


class BatchUpdateParams(TypedDict, total=False):
    task_id: Required[str]

    updates: Required[Dict[str, TaskMessageContentParam]]
