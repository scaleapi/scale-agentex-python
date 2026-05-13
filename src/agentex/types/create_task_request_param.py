# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import TypedDict

__all__ = ["CreateTaskRequestParam"]


class CreateTaskRequestParam(TypedDict, total=False):
    name: Optional[str]
    """The name of the task to create"""

    params: Optional[Dict[str, object]]
    """The parameters for the task"""

    task_metadata: Optional[Dict[str, object]]
    """Caller-provided metadata to persist on the task row.

    Only applied at task creation; ignored if a task with this name already exists.
    Forwarded to the agent inside the ACP payload for backward compatibility.
    """
