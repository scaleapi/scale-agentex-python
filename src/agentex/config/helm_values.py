"""Pure helm-values generation for the ``agentex-agent`` chart.

Maps an :class:`~agentex.config.agent_manifest.AgentManifest` plus an optional
:class:`~agentex.config.environment_config.AgentEnvironmentConfig` to the values
dict the ``agentex-agent`` helm chart consumes. Depends only on pydantic and the
stdlib, so it is safe to import from a slim REST-only install without the ADK
runtime — the same contract as the other ``agentex.config`` modules.

Filesystem-aware ACP module resolution stays in
``agentex.lib.cli.utils.path_utils``: callers that have the agent source tree on
disk should resolve the module themselves and pass ``acp_module``. Callers
without one (e.g. server-side deployers) get :func:`derive_acp_module`'s
pure-string derivation by default.
"""

from __future__ import annotations

import json
import base64
import logging
from typing import Any

from agentex.config.agent_manifest import AgentManifest
from agentex.config.environment_config import AgentAuthConfig, AgentEnvironmentConfig

logger = logging.getLogger(__name__)

TEMPORAL_WORKER_KEY = "temporal-worker"
AUTH_PRINCIPAL_ENV_VAR = "AUTH_PRINCIPAL_B64"

__all__ = [
    "AUTH_PRINCIPAL_ENV_VAR",
    "TEMPORAL_WORKER_KEY",
    "build_acp_command",
    "derive_acp_module",
    "encode_principal_context",
    "convert_env_vars_dict_to_list",
    "merge_deployment_configs",
]


def convert_env_vars_dict_to_list(env_vars: dict[str, str]) -> list[dict[str, str]]:
    """Convert a dictionary of environment variables to a list of dictionaries"""
    return [{"name": key, "value": value} for key, value in env_vars.items()]


def encode_principal_context(auth_config: AgentAuthConfig | None) -> str | None:
    """Base64-encode the auth principal as compact JSON, or None if unset."""
    if auth_config is None:
        return None

    principal = auth_config.principal
    if not principal:
        return None

    json_str = json.dumps(principal, separators=(",", ":"))
    return base64.b64encode(json_str.encode("utf-8")).decode("utf-8")


def derive_acp_module(manifest: AgentManifest) -> str:
    """Derive the ACP module from the manifest by pure string transform.

    Callers with the agent source tree on disk should prefer the filesystem-aware
    resolution in ``agentex.lib.cli.utils.path_utils.calculate_docker_acp_module``
    and pass its result to :func:`merge_deployment_configs` as ``acp_module``.
    """
    if manifest.local_development and manifest.local_development.paths:
        acp_path = manifest.local_development.paths.acp
        if acp_path:
            return acp_path.replace(".py", "").replace("/", ".")
    return "project.acp"


def build_acp_command(acp_module: str) -> list[str]:
    """Build the uvicorn command that runs the agent's ACP server."""
    return ["uvicorn", f"{acp_module}:acp", "--host", "0.0.0.0", "--port", "8000"]


def _deep_merge(base_dict: dict[str, Any], override_dict: dict[str, Any]) -> None:
    """Deep merge override_dict into base_dict"""
    for key, value in override_dict.items():
        if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
            _deep_merge(base_dict[key], value)
        else:
            base_dict[key] = value


def merge_deployment_configs(
    manifest: AgentManifest,
    agent_env_config: AgentEnvironmentConfig | None,
    *,
    repository: str,
    image_tag: str,
    acp_module: str | None = None,
) -> dict[str, Any]:
    """Merge global deployment config with environment-specific overrides into helm values.

    Args:
        manifest: The agent manifest configuration.
        agent_env_config: Environment-specific configuration (optional).
        repository: Container image repository to deploy.
        image_tag: Container image tag to deploy.
        acp_module: Pre-resolved ACP module for the uvicorn command. Defaults to
            :func:`derive_acp_module`'s pure-string derivation.

    Returns:
        Dictionary of helm values ready for deployment.

    Raises:
        ValueError: If deployment configuration is missing or invalid.
    """
    agent_config = manifest.agent

    if not manifest.deployment:
        raise ValueError("No deployment configuration found in manifest")

    if not repository or not image_tag:
        raise ValueError("Repository and image tag are required")

    # Start with global configuration
    helm_values: dict[str, Any] = {
        "global": {
            "image": {
                "repository": repository,
                "tag": image_tag,
                "pullPolicy": "IfNotPresent",
            },
            "agent": {
                "name": manifest.agent.name,
                "description": manifest.agent.description,
                "acp_type": manifest.agent.acp_type,
            },
        },
        "replicaCount": manifest.deployment.global_config.replicaCount,
        "resources": {
            "requests": {
                "cpu": manifest.deployment.global_config.resources.requests.cpu,
                "memory": manifest.deployment.global_config.resources.requests.memory,
            },
            "limits": {
                "cpu": manifest.deployment.global_config.resources.limits.cpu,
                "memory": manifest.deployment.global_config.resources.limits.memory,
            },
        },
        # Enable autoscaling by default for production deployments
        "autoscaling": {
            "enabled": True,
            "minReplicas": 1,
            "maxReplicas": 10,
            "targetCPUUtilizationPercentage": 50,
        },
    }

    # Handle temporal configuration using new helper methods
    if agent_config.is_temporal_agent():
        temporal_config = agent_config.get_temporal_workflow_config()
        if temporal_config:
            helm_values[TEMPORAL_WORKER_KEY] = {
                "enabled": True,
                # Enable autoscaling for temporal workers as well
                "autoscaling": {
                    "enabled": True,
                    "minReplicas": 1,
                    "maxReplicas": 10,
                    "targetCPUUtilizationPercentage": 50,
                },
            }
            helm_values["global"]["workflow"] = {
                "name": temporal_config.name,
                "taskQueue": temporal_config.queue_name,
            }

    # Collect all environment variables with proper precedence
    # Priority: manifest -> environments.yaml -> secrets (highest)
    all_env_vars: dict[str, str] = {}
    secret_env_vars: list[dict[str, str]] = []

    # Start with agent_config env vars from manifest
    if agent_config.env:
        all_env_vars.update(agent_config.env)

    # Override with environment config env vars if they exist
    if agent_env_config and agent_env_config.helm_overrides and "env" in agent_env_config.helm_overrides:
        env_overrides = agent_env_config.helm_overrides["env"]
        if isinstance(env_overrides, list):
            # Convert list format to dict for easier merging
            env_override_dict: dict[str, str] = {}
            for env_var in env_overrides:
                if isinstance(env_var, dict) and "name" in env_var and "value" in env_var:
                    env_override_dict[str(env_var["name"])] = str(env_var["value"])
            all_env_vars.update(env_override_dict)

    # Handle credentials and check for conflicts
    if agent_config.credentials:
        for credential in agent_config.credentials:
            # Handle both CredentialMapping objects and legacy dict format
            if isinstance(credential, dict):
                env_var_name = credential["env_var_name"]
                secret_name = credential["secret_name"]
                secret_key = credential["secret_key"]
            else:
                env_var_name = credential.env_var_name
                secret_name = credential.secret_name
                secret_key = credential.secret_key

            # Check if the environment variable name conflicts with existing env vars
            if env_var_name in all_env_vars:
                logger.warning(
                    f"Environment variable '{env_var_name}' is defined in both "
                    f"env and secretEnvVars. The secret value will take precedence."
                )
                # Remove from regular env vars since secret takes precedence
                del all_env_vars[env_var_name]

            secret_env_vars.append(
                {
                    "name": env_var_name,
                    "secretName": secret_name,
                    "secretKey": secret_key,
                }
            )

    # Apply agent environment configuration overrides
    if agent_env_config:
        # Add auth principal env var if environment config is set
        if agent_env_config.auth:
            encoded_principal = encode_principal_context(agent_env_config.auth)
            if encoded_principal:
                all_env_vars[AUTH_PRINCIPAL_ENV_VAR] = encoded_principal
            else:
                raise ValueError(f"Auth principal unable to be encoded for agent_env_config: {agent_env_config}")

        if agent_env_config.helm_overrides:
            _deep_merge(helm_values, agent_env_config.helm_overrides)

    # Set final environment variables
    # Environment variable precedence: manifest -> environments.yaml -> secrets (highest)
    if all_env_vars:
        helm_values["env"] = convert_env_vars_dict_to_list(all_env_vars)

    if secret_env_vars:
        helm_values["secretEnvVars"] = secret_env_vars

    # Set environment variables for temporal worker if enabled
    if TEMPORAL_WORKER_KEY in helm_values:
        if all_env_vars:
            helm_values[TEMPORAL_WORKER_KEY]["env"] = convert_env_vars_dict_to_list(all_env_vars)
        if secret_env_vars:
            helm_values[TEMPORAL_WORKER_KEY]["secretEnvVars"] = secret_env_vars

    # Handle image pull secrets
    if manifest.deployment and manifest.deployment.imagePullSecrets:
        pull_secrets = [pull_secret.model_dump() for pull_secret in manifest.deployment.imagePullSecrets]
        helm_values["global"]["imagePullSecrets"] = pull_secrets
        helm_values["imagePullSecrets"] = pull_secrets

    # Add dynamic ACP command based on manifest configuration if command is not set in helm overrides
    helm_overrides_command = (
        agent_env_config and agent_env_config.helm_overrides and "command" in agent_env_config.helm_overrides
    )
    if not helm_overrides_command:
        module = acp_module or derive_acp_module(manifest)
        helm_values["command"] = build_acp_command(module)
        logger.info(f"Using ACP command: uvicorn {module}:acp")

    return helm_values
