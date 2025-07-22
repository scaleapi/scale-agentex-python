import subprocess

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from rich.console import Console

from agentex.lib.cli.utils.exceptions import DeploymentError
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)
console = Console()


class KubernetesClientManager:
    """Manages Kubernetes clients for different contexts"""

    def __init__(self):
        self._clients: dict[str, client.CoreV1Api] = {}

    def get_client(self, context: str | None = None) -> client.CoreV1Api:
        """Get a Kubernetes client for the specified context"""
        if context is None:
            context = get_current_context()

        if context not in self._clients:
            try:
                # Load config for specific context
                config.load_kube_config(context=context)
                self._clients[context] = client.CoreV1Api()
                logger.info(f"Created Kubernetes client for context: {context}")
            except Exception as e:
                raise DeploymentError(
                    f"Failed to create Kubernetes client for context '{context}': {e}"
                ) from e

        return self._clients[context]

    def clear_cache(self):
        """Clear cached clients (useful when contexts change)"""
        self._clients.clear()


def get_current_context() -> str:
    """Get the current kubectl context"""
    try:
        contexts, active_context = config.list_kube_config_contexts()
        if active_context is None:
            raise DeploymentError("No active kubectl context found")
        return active_context["name"]
    except Exception as e:
        raise DeploymentError(f"Failed to get current kubectl context: {e}") from e


# Global client manager instance
_client_manager = KubernetesClientManager()


def list_available_contexts() -> list[str]:
    """List all available kubectl contexts"""
    try:
        contexts, _ = config.list_kube_config_contexts()
        return [ctx["name"] for ctx in contexts]
    except Exception as e:
        raise DeploymentError(f"Failed to list kubectl contexts: {e}") from e


def validate_cluster_context(cluster_name: str) -> bool:
    """Check if a cluster name corresponds to an available kubectl context"""
    try:
        available_contexts = list_available_contexts()
        return cluster_name in available_contexts
    except DeploymentError:
        return False


def switch_kubectl_context(cluster_name: str) -> None:
    """Switch to the specified kubectl context"""
    try:
        # Use subprocess for context switching as it's a local kubeconfig operation
        subprocess.run(
            ["kubectl", "config", "use-context", cluster_name],
            capture_output=True,
            text=True,
            check=True,
        )
        # Clear client cache since context changed
        _client_manager.clear_cache()
        logger.info(f"Switched to kubectl context: {cluster_name}")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise DeploymentError(
            f"Failed to switch to kubectl context '{cluster_name}': {e}"
        ) from e


def validate_namespace(namespace: str, context: str | None = None) -> bool:
    """Check if a namespace exists in the specified cluster context"""
    try:
        k8s_client = _client_manager.get_client(context)
        k8s_client.read_namespace(name=namespace)
        return True
    except ApiException as e:
        if e.status == 404:
            return False
        raise DeploymentError(f"Failed to validate namespace '{namespace}': {e}") from e
    except Exception as e:
        raise DeploymentError(f"Failed to validate namespace '{namespace}': {e}") from e


def check_and_switch_cluster_context(cluster_name: str) -> None:
    """Check and switch to the specified kubectl context"""
    # Validate cluster context
    if not validate_cluster_context(cluster_name):
        available_contexts = list_available_contexts()
        raise DeploymentError(
            f"Cluster '{cluster_name}' not found in kubectl contexts.\n"
            f"Available contexts: {', '.join(available_contexts)}\n"
            f"Please ensure you have a valid kubeconfig for this cluster."
        )

    # Switch to the specified cluster context
    current_context = get_current_context()
    if current_context != cluster_name:
        console.print(
            f"[blue]ℹ[/blue] Switching from context '{current_context}' to '{cluster_name}'"
        )
        switch_kubectl_context(cluster_name)
    else:
        console.print(
            f"[blue]ℹ[/blue] Using current kubectl context: [bold]{cluster_name}[/bold]"
        )


def get_k8s_client(context: str | None = None) -> client.CoreV1Api:
    """Get a Kubernetes client for the specified context (or current context if None)"""
    return _client_manager.get_client(context)
