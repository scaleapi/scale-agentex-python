# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Required, TypedDict

__all__ = ["CheckpointListParams"]


class CheckpointListParams(TypedDict, total=False):
    thread_id: Required[str]

    before_checkpoint_id: Optional[str]

    checkpoint_ns: Optional[str]

    filter_metadata: Optional[Dict[str, object]]

    limit: int
