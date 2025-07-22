from typing import Literal

from pydantic import BaseModel, Field


class BaseACPConfig(BaseModel):
    """
    Base configuration for all ACP implementations

    Attributes:
        type: The type of ACP implementation
    """

    pass


class SyncACPConfig(BaseACPConfig):
    """
    Configuration for SyncACP implementation

    Attributes:
        type: The type of ACP implementation
    """

    pass


class AgenticACPConfig(BaseACPConfig):
    """
    Base class for agentic ACP configurations

    Attributes:
        type: The type of ACP implementation
    """

    type: Literal["temporal", "base"] = Field(..., frozen=True)


class TemporalACPConfig(AgenticACPConfig):
    """
    Configuration for TemporalACP implementation

    Attributes:
        type: The type of ACP implementation
        temporal_address: The address of the temporal server
    """

    type: Literal["temporal"] = Field(default="temporal", frozen=True)
    temporal_address: str = Field(
        default="temporal-frontend.temporal.svc.cluster.local:7233", frozen=True
    )


class AgenticBaseACPConfig(AgenticACPConfig):
    """Configuration for AgenticBaseACP implementation

    Attributes:
        type: The type of ACP implementation
    """

    type: Literal["base"] = Field(default="base", frozen=True)
