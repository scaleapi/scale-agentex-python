from __future__ import annotations

import os
import tempfile
import subprocess
from typing import Any
from pathlib import Path

import yaml
from pydantic import Field, BaseModel
from rich.console import Console

from agentex.lib.utils.logging import make_logger
from agentex.lib.cli.utils.exceptions import HelmError, DeploymentError
from agentex.lib.cli.utils.path_utils import PathResolutionError, calculate_docker_acp_module
from agentex.lib.environment_variables import EnvVarKeys
from agentex.lib.cli.utils.kubectl_utils import check_and_switch_cluster_context
from agentex.lib.sdk.config.agent_config import AgentConfig
from agentex.lib.sdk.config.agent_manifest import AgentManifest
from agentex.lib.sdk.config.environment_config import OciRegistryConfig, AgentEnvironmentConfig

logger = make_logger(__name__)
console = Console()

TEMPORAL_WORKER_KEY = "temporal-worker"
DEFAULT_HELM_CHART_VERSION = "0.1.9"


class InputDeployOverrides(BaseModel):
    repository: str | None = Field(default=None, description="Override the repository for deployment")
    image_tag: str | None = Field(default=None, description="Override the image tag for deployment")


def check_helm_installed() -> bool:
    """Check if helm is installed and available"""
    try:
        result = subprocess.run(["helm", "version", "--short"], capture_output=True, text=True, check=True)
        logger.info(f"Helm version: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def add_helm_repo(helm_repository_name: str, helm_repository_url: str) -> None:
    """Add the agentex helm repository if not already added (classic mode)"""
    try:
        # Check if repo already exists
        result = subprocess.run(["helm", "repo", "list"], capture_output=True, text=True, check=True)

        if helm_repository_name not in result.stdout:
            console.print("Adding agentex helm repository...")
            subprocess.run(
                [
                    "helm",
                    "repo",
                    "add",
                    helm_repository_name,
                    helm_repository_url,
                ],
                check=True,
            )
        else:
            logger.info("Helm repository already exists. Running update...")

        subprocess.run(["helm", "repo", "update"], check=True)
        console.print("[green]✓[/green] Helm repository update successfully")

    except subprocess.CalledProcessError as e:
        raise HelmError(f"Failed to add helm repository: {e}") from e


def login_to_gar_registry(oci_registry: str) -> None:
    """Auto-login to Google Artifact Registry using gcloud credentials.

    Args:
        oci_registry: The GAR registry URL (e.g., 'us-west1-docker.pkg.dev/project-id/repo-name')
    """
    try:
        # Extract the registry host (e.g., 'us-west1-docker.pkg.dev')
        registry_host = oci_registry.split("/")[0]

        # Get access token from gcloud
        console.print(f"[blue]ℹ[/blue] Authenticating with Google Artifact Registry: {registry_host}")
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=True,
        )
        access_token = result.stdout.strip()

        # Login to helm registry using the access token
        subprocess.run(
            [
                "helm",
                "registry",
                "login",
                registry_host,
                "--username",
                "oauth2accesstoken",
                "--password-stdin",
            ],
            input=access_token,
            text=True,
            check=True,
        )
        console.print(f"[green]✓[/green] Authenticated with GAR: {registry_host}")

    except subprocess.CalledProcessError as e:
        raise HelmError(
            f"Failed to authenticate with Google Artifact Registry: {e}\n"
            "Ensure you are logged in with 'gcloud auth login' and have access to the registry."
        ) from e
    except FileNotFoundError:
        raise HelmError(
            "gcloud CLI not found. Please install the Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
        ) from None


def get_latest_gar_chart_version(oci_registry: str, chart_name: str = "agentex-agent") -> str:
    """Fetch the latest version of a Helm chart from Google Artifact Registry.

    GAR stores Helm chart versions as tags (e.g., '0.1.9'), not as versions (which are SHA digests).
    This function lists tags sorted by creation time and returns the most recent one.

    Args:
        oci_registry: The GAR registry URL (e.g., 'us-west1-docker.pkg.dev/project-id/repo-name')
        chart_name: Name of the Helm chart

    Returns:
        The latest version string (e.g., '0.2.0')
    """
    try:
        # Parse the OCI registry URL to extract components
        # Format: REGION-docker.pkg.dev/PROJECT/REPOSITORY
        parts = oci_registry.split("/")
        if len(parts) < 3:
            raise HelmError(
                f"Invalid OCI registry format: {oci_registry}. "
                "Expected format: REGION-docker.pkg.dev/PROJECT/REPOSITORY"
            )

        location = parts[0].replace("-docker.pkg.dev", "")
        project = parts[1]
        repository = parts[2]

        console.print(f"[blue]ℹ[/blue] Fetching latest chart version from GAR...")

        # Use gcloud to list tags (not versions - versions are SHA digests)
        # Tags contain the semantic versions like '0.1.9'
        result = subprocess.run(
            [
                "gcloud",
                "artifacts",
                "tags",
                "list",
                f"--repository={repository}",
                f"--location={location}",
                f"--project={project}",
                f"--package={chart_name}",
                "--sort-by=~createTime",
                "--limit=1",
                "--format=value(tag)",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        output = result.stdout.strip()
        if not output:
            raise HelmError(f"No tags found for chart '{chart_name}' in {oci_registry}")

        # The output is the tag name (semantic version)
        version = output
        console.print(f"[green]✓[/green] Latest chart version: {version}")
        return version

    except subprocess.CalledProcessError as e:
        raise HelmError(
            f"Failed to fetch chart tags from GAR: {e.stderr}\nEnsure you have access to the Artifact Registry."
        ) from e
    except FileNotFoundError:
        raise HelmError(
            "gcloud CLI not found. Please install the Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
        ) from None


def resolve_chart(
    oci_registry: OciRegistryConfig | None,
    helm_repository_name: str | None,
    use_latest_chart: bool,
    chart_name: str = "agentex-agent",
) -> tuple[str, str]:
    """Resolve the chart reference and version based on the deployment mode.

    For OCI mode, builds an oci:// reference and resolves version from:
      --use-latest-chart (GAR only) > oci_registry.chart_version > default.
    For classic mode, builds a repo/chart reference and uses default version.

    Returns:
        (chart_reference, chart_version)
    """
    if oci_registry:
        chart_reference = f"oci://{oci_registry.url}/{chart_name}"

        if use_latest_chart:
            if oci_registry.provider != "gar":
                console.print(
                    "[yellow]⚠[/yellow] --use-latest-chart only works with GAR provider (provider: gar), using default version"
                )
                chart_version = DEFAULT_HELM_CHART_VERSION
            else:
                chart_version = get_latest_gar_chart_version(oci_registry.url)
        elif oci_registry.chart_version:
            chart_version = oci_registry.chart_version
        else:
            chart_version = DEFAULT_HELM_CHART_VERSION
    else:
        if not helm_repository_name:
            raise HelmError("Helm repository name is required for classic mode")
        chart_reference = f"{helm_repository_name}/{chart_name}"

        if use_latest_chart:
            console.print("[yellow]⚠[/yellow] --use-latest-chart only works with OCI registries, using default version")
        chart_version = DEFAULT_HELM_CHART_VERSION

    console.print(f"[blue]ℹ[/blue] Using Helm chart version: {chart_version}")
    return chart_reference, chart_version


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
    agent_env_config: AgentEnvironmentConfig | None,
    deploy_overrides: InputDeployOverrides,
    manifest_path: str,
) -> dict[str, Any]:
    agent_config: AgentConfig = manifest.agent

    """Merge global deployment config with environment-specific overrides into helm values"""
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
            from agentex.lib.cli.utils.auth_utils import _encode_principal_context_from_env_config

            encoded_principal = _encode_principal_context_from_env_config(agent_env_config.auth)
            logger.info(f"Encoding auth principal from {agent_env_config.auth}")
            if encoded_principal:
                all_env_vars[EnvVarKeys.AUTH_PRINCIPAL_B64.value] = encoded_principal
            else:
                raise DeploymentError(f"Auth principal unable to be encoded for agent_env_config: {agent_env_config}")

        logger.info(f"Defined agent helm overrides: {agent_env_config.helm_overrides}")
        logger.info(f"Before-merge helm values: {helm_values}")
        if agent_env_config.helm_overrides:
            _deep_merge(helm_values, agent_env_config.helm_overrides)
        logger.info(f"After-merge helm values: {helm_values}")

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
        add_acp_command_to_helm_values(helm_values, manifest, manifest_path)

    logger.info("Deploying with the following helm values: %s", helm_values)
    return helm_values


def _deep_merge(base_dict: dict[str, Any], override_dict: dict[str, Any]) -> None:
    """Deep merge override_dict into base_dict"""
    for key, value in override_dict.items():
        if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
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
    environment_name: str | None = None,
    use_latest_chart: bool = False,
) -> None:
    """Deploy an agent using helm

    Args:
        manifest_path: Path to the agent manifest file
        cluster_name: Target Kubernetes cluster name
        namespace: Kubernetes namespace to deploy to
        deploy_overrides: Image repository/tag overrides
        environment_name: Environment name from environments.yaml
        use_latest_chart: If True, fetch and use the latest chart version from OCI registry (OCI mode only)
    """

    # Validate prerequisites
    if not check_helm_installed():
        raise DeploymentError("Helm is not installed. Please install helm first.")

    # Switch to the specified cluster context
    check_and_switch_cluster_context(cluster_name)

    manifest = AgentManifest.from_yaml(file_path=manifest_path)

    # Load agent environment configuration
    agent_env_config = None
    if environment_name:
        manifest_dir = Path(manifest_path).parent
        environments_config = manifest.load_environments_config(manifest_dir)
        if environments_config:
            agent_env_config = environments_config.get_config_for_env(environment_name)
            console.print(f"[green]✓[/green] Using environment config: {environment_name}")
        else:
            console.print(f"[yellow]⚠[/yellow] No environments.yaml found, skipping environment-specific config")

    # Determine deployment mode: OCI registry or classic helm repo
    oci_registry = agent_env_config.oci_registry if agent_env_config else None
    helm_repository_name: str | None = None

    if oci_registry:
        console.print(f"[blue]ℹ[/blue] Using OCI Helm registry: {oci_registry.url}")

        # Only auto-authenticate for GAR provider
        if oci_registry.provider == "gar":
            login_to_gar_registry(oci_registry.url)
        else:
            console.print(
                "[blue]ℹ[/blue] Skipping auto-authentication (no provider specified, assuming already authenticated)"
            )
    else:
        if agent_env_config:
            helm_repository_name = agent_env_config.helm_repository_name
            helm_repository_url = agent_env_config.helm_repository_url
        else:
            helm_repository_name = "scale-egp"
            helm_repository_url = "https://scale-egp-helm-charts-us-west-2.s3.amazonaws.com/charts"
        # Add helm repository/update (classic mode only)
        add_helm_repo(helm_repository_name, helm_repository_url)

    # Resolve chart reference and version in one step
    chart_reference, chart_version = resolve_chart(
        oci_registry=oci_registry,
        helm_repository_name=helm_repository_name,
        use_latest_chart=use_latest_chart,
    )

    # Merge configurations
    helm_values = merge_deployment_configs(manifest, agent_env_config, deploy_overrides, manifest_path)

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
                chart_reference,
                "--version",
                chart_version,
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
                chart_reference,
                "--version",
                chart_version,
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
        console.print(f"[blue]Check deployment status:[/blue] helm status {release_name} -n {namespace}")
        console.print(f"[blue]View logs:[/blue] kubectl logs -l app.kubernetes.io/name=agentex-agent -n {namespace}")

    except subprocess.CalledProcessError as e:
        raise HelmError(
            f"Helm deployment failed: {e}\n"
            f"Note: Due to --atomic flag, any partial deployment has been automatically rolled back."
        ) from e
    finally:
        # Clean up values file
        os.unlink(values_file)
