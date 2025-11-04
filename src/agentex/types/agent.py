# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel
from .acp_type import AcpType

__all__ = ["Agent"]


class Agent(BaseModel):
    id: str
    """The unique identifier of the agent."""

    acp_type: AcpType
    """The type of the ACP Server (Either sync or async)"""

    created_at: datetime
    """The timestamp when the agent was created"""

    description: str
    """The description of the action."""

    name: str
    """The unique name of the agent."""

    updated_at: datetime
    """The timestamp when the agent was last updated"""

    registered_at: Optional[datetime] = None
    """The timestamp when the agent was last registered"""

    registration_metadata: Optional[Dict[str, object]] = None
    """The metadata for the agent's registration."""

    status: Optional[Literal["Ready", "Failed", "Unknown", "Deleted"]] = None
    """The status of the action, indicating if it's building, ready, failed, etc."""

    status_reason: Optional[str] = None
    """The reason for the status of the action."""
