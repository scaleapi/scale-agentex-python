# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["Task"]


class Task(BaseModel):
    id: str

    created_at: Optional[datetime] = None

    name: Optional[str] = None

    status: Optional[Literal["CANCELED", "COMPLETED", "FAILED", "RUNNING", "TERMINATED", "TIMED_OUT"]] = None

    status_reason: Optional[str] = None

    updated_at: Optional[datetime] = None
