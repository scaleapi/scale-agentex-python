# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime
from typing_extensions import Literal, TypeAlias

from .agent import Agent
from .._models import BaseModel

__all__ = ["TaskListResponse", "TaskListResponseItem"]


class TaskListResponseItem(BaseModel):
    """Lean list-response shape.

    Omits `params` (the arbitrary create-time
    payload, which can carry per-caller secrets and PII); fetch GET /tasks/{id}
    for the full record.
    """

    id: str

    agents: Optional[List[Agent]] = None

    cleaned_at: Optional[datetime] = None

    created_at: Optional[datetime] = None

    name: Optional[str] = None

    status: Optional[
        Literal["CANCELED", "COMPLETED", "FAILED", "RUNNING", "INTERRUPTED", "TERMINATED", "TIMED_OUT", "DELETED"]
    ] = None

    status_reason: Optional[str] = None

    task_metadata: Optional[Dict[str, object]] = None

    updated_at: Optional[datetime] = None


TaskListResponse: TypeAlias = List[TaskListResponseItem]
