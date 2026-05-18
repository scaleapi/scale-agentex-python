# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional

from .._models import BaseModel

__all__ = ["CheckpointGetTupleResponse", "Blob", "PendingWrite"]


class Blob(BaseModel):
    channel: str

    type: str

    version: str

    blob: Optional[str] = None


class PendingWrite(BaseModel):
    channel: str

    idx: int

    task_id: str

    blob: Optional[str] = None

    type: Optional[str] = None


class CheckpointGetTupleResponse(BaseModel):
    checkpoint: Dict[str, object]

    checkpoint_id: str

    checkpoint_ns: str

    metadata: Dict[str, object]

    thread_id: str

    blobs: Optional[List[Blob]] = None

    parent_checkpoint_id: Optional[str] = None

    pending_writes: Optional[List[PendingWrite]] = None
