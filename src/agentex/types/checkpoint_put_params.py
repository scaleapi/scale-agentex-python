# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Iterable, Optional
from typing_extensions import Required, TypedDict

__all__ = ["CheckpointPutParams", "Blob"]


class CheckpointPutParams(TypedDict, total=False):
    checkpoint: Required[Dict[str, object]]

    checkpoint_id: Required[str]

    thread_id: Required[str]

    blobs: Iterable[Blob]

    checkpoint_ns: str

    metadata: Dict[str, object]

    parent_checkpoint_id: Optional[str]


class Blob(TypedDict, total=False):
    channel: Required[str]

    type: Required[str]

    version: Required[str]

    blob: Optional[str]
