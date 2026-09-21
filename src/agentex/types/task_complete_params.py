# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

__all__ = ["TaskCompleteParams"]


class TaskCompleteParams(TypedDict, total=False):
    reason: Optional[str]
