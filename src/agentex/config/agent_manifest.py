from __future__ import annotations

from pydantic import Field

from agentex.config._base import ConfigBaseModel
from agentex.config.agent_config import AgentConfig
from agentex.config.build_config import BuildConfig
from agentex.config.deployment_config import DeploymentConfig
from agentex.config.local_development_config import LocalDevelopmentConfig


class AgentManifest(ConfigBaseModel):
    """
    Represents a manifest file that describes how to build and deploy an agent.
    """

    build: BuildConfig
    agent: AgentConfig
    local_development: LocalDevelopmentConfig | None = Field(
        default=None, description="Configuration for local development"
    )
    deployment: DeploymentConfig | None = Field(
        default=None, description="Deployment configuration for the agent"
    )
