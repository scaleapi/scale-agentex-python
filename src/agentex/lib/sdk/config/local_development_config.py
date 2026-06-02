from __future__ import annotations

from pathlib import Path

from pydantic import Field, validator

from agentex.lib.utils.model_utils import BaseModel


class LocalAgentConfig(BaseModel):
    """Configuration for local agent development"""

    port: int = Field(
        ...,
        description="The port where the agent's ACP server is running locally",
        gt=0,
        lt=65536,
    )
    host_address: str = Field(
        default="host.docker.internal",
        description="The host address where the agent's ACP server can be reached (e.g., host.docker.internal for Docker, localhost for direct)",
    )


class LocalPathsConfig(BaseModel):
    """Configuration for local file paths"""

    acp: str = Field(
        default="project/acp.py",
        description="Path to the ACP server file. Can be relative to manifest directory or absolute.",
    )
    worker: str | None = Field(
        default=None,
        description="Path to the temporal worker file. Can be relative to manifest directory or absolute. (only for temporal agents)",
    )

    @validator("acp", "worker")
    def validate_path_format(cls, v):
        """Validate that the path is a reasonable format"""
        if v is None:
            return v

        # Convert to Path to validate format
        try:
            Path(v)
        except Exception as e:
            raise ValueError(f"Invalid path format: {v}") from e

        return v


class LocalDevelopmentConfig(BaseModel):
    """Configuration for local development environment"""

    agent: LocalAgentConfig = Field(..., description="Local agent configuration")
    paths: LocalPathsConfig | None = Field(
        default=None, description="File paths for local development"
    )
    redis_enabled: bool = Field(
        default=True,
        description=(
            "Whether the local CLI should set REDIS_URL=redis://localhost:6379 for the "
            "agent process. Set to false for agents that don't use adk.messages/adk.streaming "
            "when no local Redis is available, to avoid silent request hangs from the lazy "
            "Redis client."
        ),
    )
