"""
Environment-specific configuration models for agent deployments.

This module provides Pydantic models for managing environment-specific
configurations that are separate from the main manifest.yaml file.
"""

from __future__ import annotations

from typing import Any, Dict, override
from pathlib import Path

import yaml
from pydantic import Field, BaseModel, field_validator

from agentex.lib.utils.model_utils import BaseModel as UtilsBaseModel


class AgentAuthConfig(BaseModel):
    """Authentication configuration for an agent in a specific environment."""

    principal: Dict[str, Any] = Field(
        ..., description="Principal configuration for agent authorization and registration"
    )

    @field_validator("principal")
    @classmethod
    def validate_principal_required_fields(cls, v: Any) -> Dict[str, Any]:
        """Ensure principal has required fields for agent registration."""
        if not isinstance(v, dict):
            raise ValueError("Principal must be a dictionary")
        return v


class AgentKubernetesConfig(BaseModel):
    """Kubernetes configuration for an agent in a specific environment."""

    namespace: str = Field(..., description="Kubernetes namespace where the agent will be deployed")

    @field_validator("namespace")
    @classmethod
    def validate_namespace_format(cls, v: str) -> str:
        """Ensure namespace follows Kubernetes naming conventions."""
        if not v or not v.strip():
            raise ValueError("Namespace cannot be empty")

        # Basic Kubernetes namespace validation
        namespace = v.strip().lower()
        if not namespace.replace("-", "").replace(".", "").isalnum():
            raise ValueError(f"Namespace '{v}' must contain only lowercase letters, numbers, hyphens, and periods")

        if len(namespace) > 63:
            raise ValueError(f"Namespace '{v}' cannot exceed 63 characters")

        return namespace


class AgentEnvironmentConfig(BaseModel):
    """Complete configuration for an agent in a specific environment."""

    kubernetes: AgentKubernetesConfig | None = Field(default=None, description="Kubernetes deployment configuration")
    environment: str | None = Field(
        default=None,
        description="The environment keyword that this specific environment maps to: either dev, staging, prod",
    )
    auth: AgentAuthConfig = Field(..., description="Authentication and authorization configuration")
    helm_repository_name: str = Field(default="scale-egp", description="Helm repository name for the environment")
    helm_repository_url: str = Field(
        default="https://scale-egp-helm-charts-us-west-2.s3.amazonaws.com/charts",
        description="Helm repository url for the environment",
    )
    helm_overrides: Dict[str, Any] = Field(
        default_factory=dict, description="Helm chart value overrides for environment-specific tuning"
    )


class AgentEnvironmentsConfig(UtilsBaseModel):
    """All environment configurations for an agent."""

    schema_version: str = Field(default="v1", description="Schema version for validation and compatibility")
    environments: Dict[str, AgentEnvironmentConfig] = Field(
        ..., description="Environment-specific configurations (dev, prod, etc.)"
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        """Ensure schema version is supported."""
        supported_versions = ["v1"]
        if v not in supported_versions:
            raise ValueError(f"Schema version '{v}' not supported. Supported versions: {', '.join(supported_versions)}")
        return v

    @field_validator("environments")
    @classmethod
    def validate_environments_not_empty(cls, v: Dict[str, AgentEnvironmentConfig]) -> Dict[str, AgentEnvironmentConfig]:
        """Ensure at least one environment is defined."""
        if not v:
            raise ValueError("At least one environment must be defined")
        return v

    def get_config_for_env(self, env_name: str) -> AgentEnvironmentConfig:
        """Get configuration for a specific environment.

        Args:
            env_name: Name of the environment (e.g., 'dev', 'prod')

        Returns:
            AgentEnvironmentConfig for the specified environment

        Raises:
            ValueError: If environment is not found
        """
        if env_name not in self.environments:
            available_envs = ", ".join(self.environments.keys())
            raise ValueError(
                f"Environment '{env_name}' not found in environments.yaml. Available environments: {available_envs}"
            )
        return self.environments[env_name]

    def get_configs_for_env(self, env_target: str) -> dict[str, AgentEnvironmentConfig]:
        """Get configuration for a specific environment based on the expected mapping.
        The environment is either:
        1. explicitly specified like so using a key-map in the environments conifg:
        environments:
        dev-aws:
            environment: "dev"
            kubernetes:
            namespace: "sgp-000-hello-acp"
            auth:
            principal:
                user_id: 73d0c8bd-4726-434c-9686-eb627d89f078
                account_id: 6887f093600ecd59bbbd3095
            helm_overrides:

        or: it it can be defined at the top level:
        dev:
            kubernetes:
            namespace: "sgp-000-hello-acp"
            auth:
            principal:
                user_id: 73d0c8bd-4726-434c-9686-eb627d89f078
                account_id: 6887f093600ecd59bbbd3095
            helm_overrides:

        if the environment field is not explicitly set, we assume its the same as
        the name of the environment
        Args:
            env_target: Name of the environment target (e.g., 'dev', 'prod')

        Returns:
            AgentEnvironmentConfig for the specified environment

        Raises:
            ValueError: If environment is not found
        """
        envs_to_deploy = {}
        if env_target in self.environments:
            # this supports if the top-level key is just "dev, staging, etc" and matches
            # the environment name exactly without any explicit mapping
            envs_to_deploy[env_target] = self.environments[env_target]

        for env_name, config in self.environments.items():
            if config.environment == env_target:
                envs_to_deploy[env_name] = config

        if len(envs_to_deploy) == 0:
            ## this just finds environments for each target, so "available_envs" refers to each target environment

            available_envs = set()
            for env_name, config in self.environments.items():
                if config.environment is not None:
                    available_envs.add(config.environment)
                else:
                    available_envs.add(env_name)
            raise ValueError(
                f"Environment '{env_target}' not found in environments.yaml. Available environments: {available_envs}"
            )

        return envs_to_deploy

    def list_environments(self) -> list[str]:
        """Get list of all configured environment names."""
        return list(self.environments.keys())

    @classmethod
    @override
    def from_yaml(cls, file_path: str) -> "AgentEnvironmentsConfig":
        """Load configuration from environments.yaml file.

        Args:
            file_path: Path to environments.yaml file

        Returns:
            Parsed and validated AgentEnvironmentsConfig

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is invalid or doesn't validate
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"environments.yaml not found: {file_path}")

        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)

            if not data:
                raise ValueError("environments.yaml file is empty")

            return cls.model_validate(data)

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format in {file_path}: {e}") from e
        except Exception as e:
            raise ValueError(f"Failed to load environments.yaml from {file_path}: {e}") from e


def load_environments_config_from_manifest_dir(manifest_dir: Path) -> AgentEnvironmentsConfig | None:
    """Helper function to load environments.yaml from same directory as manifest.yaml.

    Args:
        manifest_dir: Directory containing manifest.yaml

    Returns:
        AgentEnvironmentsConfig if environments.yaml exists, None otherwise

    Raises:
        ValueError: If environments.yaml exists but is invalid
    """
    environments_file = manifest_dir / "environments.yaml"
    if not environments_file.exists():
        return None

    return AgentEnvironmentsConfig.from_yaml(str(environments_file))
