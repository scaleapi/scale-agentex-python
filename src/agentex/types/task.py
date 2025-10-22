# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["Task"]


class Task(BaseModel):
    id: str

    created_at: Optional[datetime] = None

    name: Optional[str] = None

    params: Optional[Dict[str, object]] = None

    status: Optional[Literal["CANCELED", "COMPLETED", "FAILED", "RUNNING", "TERMINATED", "TIMED_OUT", "DELETED"]] = None

    status_reason: Optional[str] = None

    task_metadata: Optional[Dict[str, object]] = None

    updated_at: Optional[datetime] = None
