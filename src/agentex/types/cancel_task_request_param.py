# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

__all__ = ["CancelTaskRequestParam"]


class CancelTaskRequestParam(TypedDict, total=False):
    task_id: Optional[str]
    """The ID of the task to cancel. Either this or task_name must be provided."""

    task_name: Optional[str]
    """The name of the task to cancel. Either this or task_id must be provided."""
