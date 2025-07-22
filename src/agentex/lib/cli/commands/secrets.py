from pathlib import Path

import questionary
import typer
from rich import print_json
from rich.console import Console
from rich.panel import Panel

from agentex.lib.cli.handlers.secret_handlers import (
    delete_secret,
    get_kubernetes_secrets_by_type,
    get_secret,
    sync_secrets,
)
from agentex.lib.cli.utils.cli_utils import handle_questionary_cancellation
from agentex.lib.cli.utils.kubectl_utils import (
    check_and_switch_cluster_context,
    validate_namespace,
)
from agentex.lib.sdk.config.agent_manifest import AgentManifest
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)
console = Console()

secrets = typer.Typer()


@secrets.command()
def list(
    namespace: str = typer.Option(
        "agentex-agents", help="Kubernetes namespace to list secrets from"
    ),
    cluster: str | None = typer.Option(
        None, help="Cluster context to use (defaults to current context)"
    ),
):
    """List names of available secrets"""
    logger.info(f"Listing secrets in namespace: {namespace}")

    if cluster:
        check_and_switch_cluster_context(cluster)
        if not validate_namespace(namespace, cluster):
            console.print(
                f"[red]Error:[/red] Namespace '{namespace}' does not exist in cluster '{cluster}'"
            )
            raise typer.Exit(1)

    secrets_list = get_kubernetes_secrets_by_type(namespace=namespace, context=cluster)
    print_json(data=secrets_list)


@secrets.command()
def get(
    name: str = typer.Argument(..., help="Name of the secret to get"),
    namespace: str = typer.Option(
        "agentex-agents", help="Kubernetes namespace for the secret"
    ),
    cluster: str | None = typer.Option(
        None, help="Cluster context to use (defaults to current context)"
    ),
):
    """Get details about a secret"""
    logger.info(f"Getting secret: {name} from namespace: {namespace}")

    if cluster:
        check_and_switch_cluster_context(cluster)
        if not validate_namespace(namespace, cluster):
            console.print(
                f"[red]Error:[/red] Namespace '{namespace}' does not exist in cluster '{cluster}'"
            )
            raise typer.Exit(1)

    secret = get_secret(name=name, namespace=namespace, context=cluster)
    print_json(data=secret)


@secrets.command()
def delete(
    name: str = typer.Argument(..., help="Name of the secret to delete"),
    namespace: str = typer.Option(
        "agentex-agents", help="Kubernetes namespace for the secret"
    ),
    cluster: str | None = typer.Option(
        None, help="Cluster context to use (defaults to current context)"
    ),
):
    """Delete a secret"""
    logger.info(f"Deleting secret: {name} from namespace: {namespace}")

    if cluster:
        check_and_switch_cluster_context(cluster)
        if not validate_namespace(namespace, cluster):
            console.print(
                f"[red]Error:[/red] Namespace '{namespace}' does not exist in cluster '{cluster}'"
            )
            raise typer.Exit(1)

    delete_secret(name=name, namespace=namespace, context=cluster)


@secrets.command()
def sync(
    manifest: str = typer.Option(..., help="Path to the manifest file"),
    # TODO: should cluster be here or be in manifest as well?
    cluster: str = typer.Option(..., "--cluster", help="Cluster to sync secrets to"),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", help="Enable interactive prompts"
    ),
    namespace: str | None = typer.Option(
        None,
        help="Kubernetes namespace to deploy to (required in non-interactive mode)",
    ),
    values: str = typer.Option(None, "--values", help="Path to the values file"),
):
    """Sync secrets from the cluster to the local environment"""
    console.print(
        Panel.fit("🚀 [bold blue]Sync Secrets[/bold blue]", border_style="blue")
    )

    manifest_path = Path(manifest)
    if not manifest_path.exists():
        console.print(f"[red]Error:[/red] Manifest file not found: {manifest}")
        raise typer.Exit(1)

    # In non-interactive mode, require namespace
    if not interactive and not namespace:
        console.print(
            "[red]Error:[/red] --namespace is required in non-interactive mode"
        )
        raise typer.Exit(1)

    # Get namespace if not provided (only in interactive mode)
    if not namespace:
        namespace = questionary.text(
            "Enter Kubernetes namespace:", default="default"
        ).ask()
        namespace = handle_questionary_cancellation(namespace, "namespace input")

        if not namespace:
            console.print("Deployment cancelled")
            raise typer.Exit(0)

    if values:
        values_path = Path(values)
        if not values_path.exists():
            console.print(f"[red]Error:[/red] Values file not found: {values_path}")
            raise typer.Exit(1)

    # Validate cluster and namespace
    check_and_switch_cluster_context(cluster)
    if not validate_namespace(namespace, cluster):
        console.print(
            f"[red]Error:[/red] Namespace '{namespace}' does not exist in cluster '{cluster}'"
        )
        raise typer.Exit(1)

    agent_manifest = AgentManifest.from_yaml(file_path=manifest)

    # Always call sync_secrets - it will handle the case of no credentials
    sync_secrets(
        manifest_obj=agent_manifest,
        cluster=cluster,
        namespace=namespace,
        interactive=interactive,
        values_path=str(values) if values else None,
    )

    console.print("[green]Successfully synced secrets[/green]")
