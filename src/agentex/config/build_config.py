from __future__ import annotations

from pydantic import Field

from agentex.config._base import ConfigBaseModel


class BuildContext(ConfigBaseModel):
    """
    Represents the context in which the Docker image should be built.
    """

    root: str = Field(
        ...,
        description="The root directory of the build context. Should be specified relative to the location of the "
        "build config file.",
    )
    include_paths: list[str] = Field(
        default_factory=list,
        description="The paths to include in the build context. Should be specified relative to the root directory.",
    )
    dockerfile: str = Field(
        ...,
        description="The path to the Dockerfile. Should be specified relative to the root directory.",
    )
    dockerignore: str | None = Field(
        default=None,
        description="The path to the .dockerignore file. Should be specified relative to the root directory.",
    )


class BuildConfig(ConfigBaseModel):
    """
    Represents a configuration for building the action as a Docker image.
    """

    context: BuildContext
