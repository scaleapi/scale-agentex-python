# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from typing_extensions import TypeAlias

from .._models import BaseModel

__all__ = ["CheckpointListResponse", "CheckpointListResponseItem"]


class CheckpointListResponseItem(BaseModel):
    checkpoint: Dict[str, object]

    checkpoint_id: str

    checkpoint_ns: str

    metadata: Dict[str, object]

    thread_id: str

    parent_checkpoint_id: Optional[str] = None


CheckpointListResponse: TypeAlias = List[CheckpointListResponseItem]
