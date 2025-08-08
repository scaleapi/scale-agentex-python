# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel
from .acp_type import AcpType

__all__ = ["Agent"]


class Agent(BaseModel):
    id: str
    """The unique identifier of the agent."""

    acp_type: AcpType
    """The type of the ACP Server (Either sync or agentic)"""

    created_at: datetime
    """The timestamp when the agent was created"""

    description: str
    """The description of the action."""

    name: str
    """The unique name of the agent."""

    updated_at: datetime
    """The timestamp when the agent was last updated"""

    status: Optional[Literal["Pending", "Building", "Ready", "Failed", "Unknown"]] = None
    """The status of the action, indicating if it's building, ready, failed, etc."""

    status_reason: Optional[str] = None
    """The reason for the status of the action."""
