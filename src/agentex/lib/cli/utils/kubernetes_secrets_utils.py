import base64

from kubernetes import client
from kubernetes.client.rest import ApiException
from rich.console import Console

from agentex.lib.cli.utils.kubectl_utils import get_k8s_client
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)
console = Console()

KUBERNETES_SECRET_TYPE_OPAQUE = "Opaque"
KUBERNETES_SECRET_TYPE_DOCKERCONFIGJSON = "kubernetes.io/dockerconfigjson"
KUBERNETES_SECRET_TYPE_BASIC_AUTH = "kubernetes.io/basic-auth"
KUBERNETES_SECRET_TYPE_TLS = "kubernetes.io/tls"

VALID_SECRET_TYPES = [
    KUBERNETES_SECRET_TYPE_OPAQUE,
    KUBERNETES_SECRET_TYPE_DOCKERCONFIGJSON,
    KUBERNETES_SECRET_TYPE_BASIC_AUTH,
    KUBERNETES_SECRET_TYPE_TLS,
]

KUBERNETES_SECRET_TO_MANIFEST_KEY = {
    KUBERNETES_SECRET_TYPE_OPAQUE: "credentials",
    KUBERNETES_SECRET_TYPE_DOCKERCONFIGJSON: "imagePullSecrets",
}


def _create_secret_object(
    name: str, data: dict[str, str], secret_type: str = KUBERNETES_SECRET_TYPE_OPAQUE
) -> client.V1Secret:
    """Helper to create a V1Secret object with multiple key-value pairs"""
    return client.V1Secret(
        metadata=client.V1ObjectMeta(name=name),
        type=secret_type,
        string_data=data,  # Use string_data for automatic base64 encoding
    )


def create_secret_with_data(
    name: str, data: dict[str, str], namespace: str, context: str | None = None
) -> None:
    """Create a new Kubernetes secret with multiple key-value pairs"""
    v1 = get_k8s_client(context)

    try:
        # Check if secret exists
        v1.read_namespaced_secret(name=name, namespace=namespace)
        console.print(
            f"[red]Error: Secret '{name}' already exists in namespace '{namespace}'[/red]"
        )
        return
    except ApiException as e:
        if e.status != 404:  # If error is not "Not Found"
            raise

    # Create the secret
    secret = _create_secret_object(name, data)

    try:
        v1.create_namespaced_secret(namespace=namespace, body=secret)
        console.print(
            f"[green]Created secret '{name}' in namespace '{namespace}' with {len(data)} keys[/green]"
        )
    except ApiException as e:
        console.print(f"[red]Error creating secret: {e.reason}[/red]")
        raise RuntimeError(f"Failed to create secret: {str(e)}") from e


def update_secret_with_data(
    name: str, data: dict[str, str], namespace: str, context: str | None = None
) -> None:
    """Create or update a Kubernetes secret with multiple key-value pairs"""
    v1 = get_k8s_client(context)
    secret = _create_secret_object(name, data)

    try:
        # Try to update first
        v1.replace_namespaced_secret(name=name, namespace=namespace, body=secret)
        console.print(
            f"[green]Updated secret '{name}' in namespace '{namespace}' with {len(data)} keys[/green]"
        )
    except ApiException as e:
        if e.status == 404:
            # Secret doesn't exist, create it
            try:
                v1.create_namespaced_secret(namespace=namespace, body=secret)
                console.print(
                    f"[green]Created secret '{name}' in namespace '{namespace}' with {len(data)} keys[/green]"
                )
            except ApiException as create_error:
                console.print(
                    f"[red]Error creating secret: {create_error.reason}[/red]"
                )
                raise RuntimeError(
                    f"Failed to create secret: {str(create_error)}"
                ) from create_error
        else:
            console.print(f"[red]Error updating secret: {e.reason}[/red]")
            raise RuntimeError(f"Failed to update secret: {str(e)}") from e


def create_image_pull_secret_with_data(
    name: str, data: dict[str, str], namespace: str, context: str | None = None
) -> None:
    """Create a new Kubernetes image pull secret with dockerconfigjson type"""
    v1 = get_k8s_client(context)

    try:
        # Check if secret exists
        v1.read_namespaced_secret(name=name, namespace=namespace)
        console.print(
            f"[red]Error: Secret '{name}' already exists in namespace '{namespace}'[/red]"
        )
        return
    except ApiException as e:
        if e.status != 404:  # If error is not "Not Found"
            raise

    # Create the secret with dockerconfigjson type
    secret = _create_secret_object(name, data, KUBERNETES_SECRET_TYPE_DOCKERCONFIGJSON)

    try:
        v1.create_namespaced_secret(namespace=namespace, body=secret)
        console.print(
            f"[green]Created image pull secret '{name}' in namespace '{namespace}' with {len(data)} keys[/green]"
        )
    except ApiException as e:
        console.print(f"[red]Error creating image pull secret: {e.reason}[/red]")
        raise RuntimeError(f"Failed to create image pull secret: {str(e)}") from e


def update_image_pull_secret_with_data(
    name: str, data: dict[str, str], namespace: str, context: str | None = None
) -> None:
    """Create or update a Kubernetes image pull secret with dockerconfigjson type"""
    v1 = get_k8s_client(context)
    secret = _create_secret_object(name, data, KUBERNETES_SECRET_TYPE_DOCKERCONFIGJSON)

    try:
        # Try to update first
        v1.replace_namespaced_secret(name=name, namespace=namespace, body=secret)
        console.print(
            f"[green]Updated image pull secret '{name}' in namespace '{namespace}' with {len(data)} keys[/green]"
        )
    except ApiException as e:
        if e.status == 404:
            # Secret doesn't exist, create it
            try:
                v1.create_namespaced_secret(namespace=namespace, body=secret)
                console.print(
                    f"[green]Created image pull secret '{name}' in namespace '{namespace}' with {len(data)} keys[/green]"
                )
            except ApiException as create_error:
                console.print(
                    f"[red]Error creating image pull secret: {create_error.reason}[/red]"
                )
                raise RuntimeError(
                    f"Failed to create image pull secret: {str(create_error)}"
                ) from create_error
        else:
            console.print(f"[red]Error updating image pull secret: {e.reason}[/red]")
            raise RuntimeError(f"Failed to update image pull secret: {str(e)}") from e


def get_secret_data(
    name: str, namespace: str, context: str | None = None
) -> dict[str, str]:
    """Get the actual data from a secret"""
    v1 = get_k8s_client(context)
    try:
        secret = v1.read_namespaced_secret(name=name, namespace=namespace)
        if secret.data:
            # Decode base64 data
            return {
                key: base64.b64decode(value).decode("utf-8")
                for key, value in secret.data.items()
            }
        return {}
    except ApiException as e:
        if e.status == 404:
            return {}
        raise RuntimeError(f"Failed to get secret data: {str(e)}") from e
