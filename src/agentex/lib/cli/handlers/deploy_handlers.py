import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from rich.console import Console

from agentex.lib.cli.utils.auth_utils import _encode_principal_context
from agentex.lib.cli.utils.exceptions import DeploymentError, HelmError
from agentex.lib.cli.utils.kubectl_utils import check_and_switch_cluster_context
from agentex.lib.cli.utils.path_utils import calculate_docker_acp_module, PathResolutionError
from agentex.lib.environment_variables import EnvVarKeys
from agentex.lib.sdk.config.agent_config import AgentConfig
from agentex.lib.sdk.config.agent_manifest import AgentManifest
from agentex.lib.sdk.config.deployment_config import ClusterConfig
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)
console = Console()

TEMPORAL_WORKER_KEY = "temporal-worker"
AGENTEX_AGENTS_HELM_CHART_VERSION = "0.1.6-v1-beta"


class InputDeployOverrides(BaseModel):
    repository: str | None = Field(
        default=None, description="Override the repository for deployment"
    )
    image_tag: str | None = Field(
        default=None, description="Override the image tag for deployment"
    )


def check_helm_installed() -> bool:
    """Check if helm is installed and available"""
    try:
        result = subprocess.run(
            ["helm", "version", "--short"], capture_output=True, text=True, check=True
        )
        logger.info(f"Helm version: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def add_helm_repo() -> None:
    """Add the agentex helm repository if not already added"""
    try:
        # Check if repo already exists
        result = subprocess.run(
            ["helm", "repo", "list"], capture_output=True, text=True, check=True
        )

        if "scale-egp" not in result.stdout:
            console.print("Adding agentex helm repository...")
            subprocess.run(
                [
                    "helm",
                    "repo",
                    "add",
                    "scale-egp",
                    "https://scale-egp-helm-charts-us-west-2.s3.amazonaws.com/charts",
                ],
                check=True,
            )
        else:
            logger.info("Helm repository already exists. Running update...")

        subprocess.run(["helm", "repo", "update"], check=True)
        console.print("[green]✓[/green] Helm repository update successfully")

    except subprocess.CalledProcessError as e:
        raise HelmError(f"Failed to add helm repository: {e}") from e


def load_override_config(override_file_path: str | None = None) -> ClusterConfig | None:
    """Load override configuration from specified file path"""
    if not override_file_path:
        return None

    override_path = Path(override_file_path)
    if not override_path.exists():
        raise DeploymentError(f"Override file not found: {override_file_path}")

    try:
        with open(override_path) as f:
            config_data = yaml.safe_load(f)
            return ClusterConfig(**config_data) if config_data else None
    except Exception as e:
        raise DeploymentError(
            f"Failed to load override config from {override_file_path}: {e}"
        ) from e



def convert_env_vars_dict_to_list(env_vars: dict[str, str]) -> list[dict[str, str]]:
    """Convert a dictionary of environment variables to a list of dictionaries"""
    return [{"name": key, "value": value} for key, value in env_vars.items()]


def add_acp_command_to_helm_values(helm_values: dict[str, Any], manifest: AgentManifest, manifest_path: str) -> None:
    """Add dynamic ACP command to helm values based on manifest configuration"""
    try:
        docker_acp_module = calculate_docker_acp_module(manifest, manifest_path)
        # Create the uvicorn command with the correct module path
        helm_values["command"] = ["uvicorn", f"{docker_acp_module}:acp", "--host", "0.0.0.0", "--port", "8000"]
        logger.info(f"Using dynamic ACP command: uvicorn {docker_acp_module}:acp")
    except (PathResolutionError, Exception) as e:
        # Fallback to default command structure
        logger.warning(f"Could not calculate dynamic ACP module ({e}), using default: project.acp")
        helm_values["command"] = ["uvicorn", "project.acp:acp", "--host", "0.0.0.0", "--port", "8000"]


def merge_deployment_configs(
    manifest: AgentManifest,
    cluster_config: ClusterConfig | None,
    deploy_overrides: InputDeployOverrides,
    manifest_path: str,
) -> dict[str, Any]:
    agent_config: AgentConfig = manifest.agent

    """Merge global deployment config with cluster-specific overrides into helm values"""
    if not manifest.deployment:
        raise DeploymentError("No deployment configuration found in manifest")

    repository = deploy_overrides.repository or manifest.deployment.image.repository
    image_tag = deploy_overrides.image_tag or manifest.deployment.image.tag

    if not repository or not image_tag:
        raise DeploymentError("Repository and image tag are required")

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

    # Collect all environment variables with conflict detection
    all_env_vars: dict[str, str] = {}
    secret_env_vars: list[dict[str, str]] = []
    
    # Start with agent_config env vars
    if agent_config.env:
        all_env_vars.update(agent_config.env)

    # Add auth principal env var if manifest principal is set
    encoded_principal = _encode_principal_context(manifest)
    if encoded_principal:
        all_env_vars[EnvVarKeys.AUTH_PRINCIPAL_B64.value] = encoded_principal

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

    # Apply cluster-specific overrides
    if cluster_config:
        if cluster_config.image:
            if cluster_config.image.repository:
                helm_values["global"]["image"]["repository"] = (
                    cluster_config.image.repository
                )
            if cluster_config.image.tag:
                helm_values["global"]["image"]["tag"] = cluster_config.image.tag

        if cluster_config.replicaCount is not None:
            helm_values["replicaCount"] = cluster_config.replicaCount

        if cluster_config.resources:
            if cluster_config.resources.requests:
                helm_values["resources"]["requests"].update(
                    {
                        "cpu": cluster_config.resources.requests.cpu,
                        "memory": cluster_config.resources.requests.memory,
                    }
                )
            if cluster_config.resources.limits:
                helm_values["resources"]["limits"].update(
                    {
                        "cpu": cluster_config.resources.limits.cpu,
                        "memory": cluster_config.resources.limits.memory,
                    }
                )

        # Handle cluster env vars with conflict detection
        if cluster_config.env:
            # Convert cluster env list to dict for easier conflict detection
            cluster_env_dict = {env_var["name"]: env_var["value"] for env_var in cluster_config.env}
            
            # Check for conflicts with secret env vars
            for secret_env_var in secret_env_vars:
                if secret_env_var["name"] in cluster_env_dict:
                    logger.warning(
                        f"Environment variable '{secret_env_var['name']}' is defined in both "
                        f"cluster config env and secretEnvVars. The secret value will take precedence."
                    )
                    del cluster_env_dict[secret_env_var["name"]]
            
            # Update all_env_vars with cluster overrides
            all_env_vars.update(cluster_env_dict)

        # Apply additional arbitrary overrides
        if cluster_config.additional_overrides:
            _deep_merge(helm_values, cluster_config.additional_overrides)

    # Set final environment variables
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
        pull_secrets = [
            pull_secret.to_dict()
            for pull_secret in manifest.deployment.imagePullSecrets
        ]
        helm_values["global"]["imagePullSecrets"] = pull_secrets
        helm_values["imagePullSecrets"] = pull_secrets

    # Add dynamic ACP command based on manifest configuration
    add_acp_command_to_helm_values(helm_values, manifest, manifest_path)
    
    print("Deploying with the following helm values: ", helm_values)
    return helm_values


def _deep_merge(base_dict: dict[str, Any], override_dict: dict[str, Any]) -> None:
    """Deep merge override_dict into base_dict"""
    for key, value in override_dict.items():
        if (
            key in base_dict
            and isinstance(base_dict[key], dict)
            and isinstance(value, dict)
        ):
            _deep_merge(base_dict[key], value)
        else:
            base_dict[key] = value


def create_helm_values_file(helm_values: dict[str, Any]) -> str:
    """Create a temporary helm values file"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(helm_values, f, default_flow_style=False)
        return f.name


def deploy_agent(
    manifest_path: str,
    cluster_name: str,
    namespace: str,
    deploy_overrides: InputDeployOverrides,
    override_file_path: str | None = None,
) -> None:
    """Deploy an agent using helm"""

    # Validate prerequisites
    if not check_helm_installed():
        raise DeploymentError("Helm is not installed. Please install helm first.")

    # Switch to the specified cluster context
    check_and_switch_cluster_context(cluster_name)

    manifest = AgentManifest.from_yaml(file_path=manifest_path)
    override_config = load_override_config(override_file_path)

    # Provide feedback about override configuration
    if override_config:
        console.print(f"[green]✓[/green] Using override config: {override_file_path}")
    else:
        console.print(
            "[yellow]ℹ[/yellow] No override config specified, using global defaults"
        )

    # Add helm repository/update
    add_helm_repo()

    # Merge configurations
    helm_values = merge_deployment_configs(manifest, override_config, deploy_overrides, manifest_path)

    # Create values file
    values_file = create_helm_values_file(helm_values)

    try:
        agent_name = manifest.agent.name
        release_name = agent_name

        console.print(
            f"Deploying agent [bold]{agent_name}[/bold] to cluster [bold]{cluster_name}[/bold] in namespace [bold]{namespace}[/bold]"
        )

        # Check if release exists
        try:
            subprocess.run(
                ["helm", "status", release_name, "-n", namespace],
                capture_output=True,
                check=True,
            )

            # Release exists, do upgrade
            console.print("Existing deployment found, upgrading...")
            command = [
                "helm",
                "upgrade",
                release_name,
                "scale-egp/agentex-agent",
                "--version",
                AGENTEX_AGENTS_HELM_CHART_VERSION,
                "-f",
                values_file,
                "-n",
                namespace,
                "--atomic",
                "--timeout",
                "10m",
            ]
            console.print(f"[blue]ℹ[/blue] Running command: {' '.join(command)}")
            subprocess.run(command, check=True)
            console.print("[green]✓[/green] Agent upgraded successfully")

        except subprocess.CalledProcessError:
            # Release doesn't exist, do install
            console.print("Installing new deployment...")
            command = [
                "helm",
                "install",
                release_name,
                "scale-egp/agentex-agent",
                "--version",
                AGENTEX_AGENTS_HELM_CHART_VERSION,
                "-f",
                values_file,
                "-n",
                namespace,
                "--create-namespace",
                "--atomic",
                "--timeout",
                "10m",
            ]
            console.print(f"[blue]ℹ[/blue] Running command: {' '.join(command)}")
            subprocess.run(command, check=True)
            console.print("[green]✓[/green] Agent deployed successfully")

        # Show success message with helpful commands
        console.print("\n[green]🎉 Deployment completed successfully![/green]")
        console.print(
            f"[blue]Check deployment status:[/blue] helm status {release_name} -n {namespace}"
        )
        console.print(
            f"[blue]View logs:[/blue] kubectl logs -l app.kubernetes.io/name=agentex-agent -n {namespace}"
        )

    except subprocess.CalledProcessError as e:
        raise HelmError(
            f"Helm deployment failed: {e}\n"
            f"Note: Due to --atomic flag, any partial deployment has been automatically rolled back."
        ) from e
    finally:
        # Clean up values file
        os.unlink(values_file)
