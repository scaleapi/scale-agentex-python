# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional
from typing_extensions import Required, TypedDict

__all__ = ["CheckpointPutWritesParams", "Write"]


class CheckpointPutWritesParams(TypedDict, total=False):
    checkpoint_id: Required[str]

    thread_id: Required[str]

    writes: Required[Iterable[Write]]

    checkpoint_ns: str

    upsert: bool


class Write(TypedDict, total=False):
    blob: Required[str]

    channel: Required[str]

    idx: Required[int]

    task_id: Required[str]

    task_path: str

    type: Optional[str]
