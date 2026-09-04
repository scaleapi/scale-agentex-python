# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["CheckpointGetTupleParams"]


class CheckpointGetTupleParams(TypedDict, total=False):
    thread_id: Required[str]

    checkpoint_id: Optional[str]

    checkpoint_ns: str
