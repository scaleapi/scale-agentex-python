import builtins
from pathlib import Path

import questionary
import typer
from rich import print_json
from rich.console import Console
from rich.panel import Panel

from agentex.lib.cli.handlers.agent_handlers import (
    build_agent,
    run_agent,
)
from agentex.lib.cli.debug import DebugConfig, DebugMode
from agentex.lib.cli.handlers.cleanup_handlers import cleanup_agent_workflows
from agentex.lib.cli.handlers.deploy_handlers import (
    DeploymentError,
    HelmError,
    InputDeployOverrides,
    deploy_agent,
)
from agentex.lib.cli.utils.cli_utils import handle_questionary_cancellation
from agentex.lib.cli.utils.kubectl_utils import (
    check_and_switch_cluster_context,
    validate_namespace,
)
from agentex import Agentex
from agentex.lib.sdk.config.agent_manifest import AgentManifest
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)
console = Console()

agents = typer.Typer()


@agents.command()
def get(
    agent_id: str = typer.Argument(..., help="ID of the agent to get"),
):
    """
    Get the agent with the given name.
    """
    logger.info(f"Getting agent with ID: {agent_id}")
    client = Agentex()
    agent = client.agents.retrieve(agent_id=agent_id)
    logger.info(f"Agent retrieved: {agent}")
    print_json(data=agent.to_dict())


@agents.command()
def list():
    """
    List all agents.
    """
    logger.info("Listing all agents")
    client = Agentex()
    agents = client.agents.list()
    logger.info(f"Agents retrieved: {agents}")
    print_json(data=[agent.to_dict() for agent in agents])


@agents.command()
def delete(
    agent_name: str = typer.Argument(..., help="Name of the agent to delete"),
):
    """
    Delete the agent with the given name.
    """
    logger.info(f"Deleting agent with name: {agent_name}")
    client = Agentex()
    client.agents.delete_by_name(agent_name=agent_name)
    logger.info(f"Agent deleted: {agent_name}")


@agents.command()
def cleanup_workflows(
    agent_name: str = typer.Argument(..., help="Name of the agent to cleanup workflows for"),
    force: bool = typer.Option(False, help="Force cleanup using direct Temporal termination (bypasses development check)"),
):
    """
    Clean up all running workflows for an agent.
    
    By default, uses graceful cancellation via agent RPC.
    With --force, directly terminates workflows via Temporal client.
    This is a convenience command that does the same thing as 'agentex tasks cleanup'.
    """
    try:
        console.print(f"[blue]Cleaning up workflows for agent '{agent_name}'...[/blue]")
        
        cleanup_agent_workflows(
            agent_name=agent_name,
            force=force,
            development_only=True
        )
        
        console.print(f"[green]✓ Workflow cleanup completed for agent '{agent_name}'[/green]")
        
    except Exception as e:
        console.print(f"[red]Cleanup failed: {str(e)}[/red]")
        logger.exception("Agent workflow cleanup failed")
        raise typer.Exit(1) from e


@agents.command()
def build(
    manifest: str = typer.Option(..., help="Path to the manifest you want to use"),
    registry: str | None = typer.Option(
        None, help="Registry URL for pushing the built image"
    ),
    repository_name: str | None = typer.Option(
        None, help="Repository name to use for the built image"
    ),
    platforms: str | None = typer.Option(
        None, help="Platform to build the image for. Please enter a comma separated list of platforms."
    ),
    push: bool = typer.Option(False, help="Whether to push the image to the registry"),
    secret: str | None = typer.Option(
        None,
        help="Docker build secret in the format 'id=secret-id,src=path-to-secret-file'",
    ),
    tag: str | None = typer.Option(
        None, help="Image tag to use (defaults to 'latest')"
    ),
    build_arg: builtins.list[str] | None = typer.Option(  # noqa: B008
        None,
        help="Docker build argument in the format 'KEY=VALUE' (can be used multiple times)",
    ),
):
    """
    Build an agent image locally from the given manifest.
    """
    typer.echo(f"Building agent image from manifest: {manifest}")

    # Validate required parameters for building
    if push and not registry:
        typer.echo("Error: --registry is required when --push is enabled", err=True)
        raise typer.Exit(1)
    
    # Only proceed with build if we have a registry (for now, to match existing behavior)
    if not registry:
        typer.echo("No registry provided, skipping image build")
        return

    platform_list = platforms.split(",") if platforms else ["linux/amd64"]

    try:
        image_url = build_agent(
            manifest_path=manifest,
            registry_url=registry,
            repository_name=repository_name,
            platforms=platform_list,
            push=push,
            secret=secret or "",  # Provide default empty string
            tag=tag or "latest",  # Provide default
            build_args=build_arg or [],  # Provide default empty list
        )
        if image_url:
            typer.echo(f"Successfully built image: {image_url}")
        else:
            typer.echo("Image build completed but no URL returned")
    except Exception as e:
        typer.echo(f"Error building agent image: {str(e)}", err=True)
        logger.exception("Error building agent image")
        raise typer.Exit(1) from e


@agents.command()
def run(
    manifest: str = typer.Option(..., help="Path to the manifest you want to use"),
    cleanup_on_start: bool = typer.Option(
        False, 
        help="Clean up existing workflows for this agent before starting"
    ),
    # Debug options
    debug: bool = typer.Option(False, help="Enable debug mode for both worker and ACP (disables auto-reload)"),
    debug_worker: bool = typer.Option(False, help="Enable debug mode for temporal worker only"),
    debug_acp: bool = typer.Option(False, help="Enable debug mode for ACP server only"),
    debug_port: int = typer.Option(5678, help="Port for remote debugging (worker uses this, ACP uses port+1)"),
    wait_for_debugger: bool = typer.Option(False, help="Wait for debugger to attach before starting"),
) -> None:
    """
    Run an agent locally from the given manifest.
    """
    typer.echo(f"Running agent from manifest: {manifest}")
    
    # Optionally cleanup existing workflows before starting
    if cleanup_on_start:
        try:
            # Parse manifest to get agent name
            manifest_obj = AgentManifest.from_yaml(file_path=manifest)
            agent_name = manifest_obj.agent.name
            
            console.print(f"[yellow]Cleaning up existing workflows for agent '{agent_name}'...[/yellow]")
            cleanup_agent_workflows(
                agent_name=agent_name,
                force=False,
                development_only=True
            )
            console.print("[green]✓ Pre-run cleanup completed[/green]")
            
        except Exception as e:
            console.print(f"[yellow]⚠ Pre-run cleanup failed: {str(e)}[/yellow]")
            logger.warning(f"Pre-run cleanup failed: {e}")
    
    # Create debug configuration based on CLI flags
    debug_config = None
    if debug or debug_worker or debug_acp:
        # Determine debug mode
        if debug:
            mode = DebugMode.BOTH
        elif debug_worker and debug_acp:
            mode = DebugMode.BOTH
        elif debug_worker:
            mode = DebugMode.WORKER
        elif debug_acp:
            mode = DebugMode.ACP
        else:
            mode = DebugMode.NONE
        
        debug_config = DebugConfig(
            enabled=True,
            mode=mode,
            port=debug_port,
            wait_for_attach=wait_for_debugger,
            auto_port=False  # Use fixed port to match VS Code launch.json
        )
        
        console.print(f"[blue]🐛 Debug mode enabled: {mode.value}[/blue]")
        if wait_for_debugger:
            console.print("[yellow]⏳ Processes will wait for debugger attachment[/yellow]")
    
    try:
        run_agent(manifest_path=manifest, debug_config=debug_config)
    except Exception as e:
        typer.echo(f"Error running agent: {str(e)}", err=True)
        logger.exception("Error running agent")
        raise typer.Exit(1) from e


@agents.command()
def deploy(
    cluster: str = typer.Option(
        ..., help="Target cluster name (must match kubectl context)"
    ),
    manifest: str = typer.Option("manifest.yaml", help="Path to the manifest file"),
    namespace: str | None = typer.Option(
        None,
        help="Kubernetes namespace to deploy to (required in non-interactive mode)",
    ),
    tag: str | None = typer.Option(None, help="Override the image tag for deployment"),
    repository: str | None = typer.Option(
        None, help="Override the repository for deployment"
    ),
    override_file: str | None = typer.Option(
        None, help="Path to override configuration file"
    ),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", help="Enable interactive prompts"
    ),
):
    """Deploy an agent to a Kubernetes cluster using Helm"""

    console.print(
        Panel.fit("🚀 [bold blue]Deploy Agent[/bold blue]", border_style="blue")
    )

    try:
        # Validate manifest exists
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

        # Validate override file exists if provided
        if override_file:
            override_path = Path(override_file)
            if not override_path.exists():
                console.print(
                    f"[red]Error:[/red] Override file not found: {override_file}"
                )
                raise typer.Exit(1)

        # Load manifest for credential validation
        manifest_obj = AgentManifest.from_yaml(str(manifest_path))

        # Confirm deployment (only in interactive mode)
        console.print("\n[bold]Deployment Summary:[/bold]")
        console.print(f"  Manifest: {manifest}")
        console.print(f"  Cluster: {cluster}")
        console.print(f"  Namespace: {namespace}")
        if tag:
            console.print(f"  Image Tag: {tag}")
        if override_file:
            console.print(f"  Override File: {override_file}")

        if interactive:
            proceed = questionary.confirm("Proceed with deployment?").ask()
            proceed = handle_questionary_cancellation(
                proceed, "deployment confirmation"
            )

            if not proceed:
                console.print("Deployment cancelled")
                raise typer.Exit(0)
        else:
            console.print("Proceeding with deployment (non-interactive mode)")

        check_and_switch_cluster_context(cluster)
        if not validate_namespace(namespace, cluster):
            console.print(
                f"[red]Error:[/red] Namespace '{namespace}' does not exist in cluster '{cluster}'"
            )
            raise typer.Exit(1)

        deploy_overrides = InputDeployOverrides(repository=repository, image_tag=tag)

        # Deploy agent
        deploy_agent(
            manifest_path=str(manifest_path),
            cluster_name=cluster,
            namespace=namespace,
            deploy_overrides=deploy_overrides,
            override_file_path=override_file,
        )

        # Use the already loaded manifest object
        release_name = f"{manifest_obj.agent.name}-{cluster}"

        console.print(
            "\n[bold green]🎉 Deployment completed successfully![/bold green]"
        )
        console.print("\nTo check deployment status:")
        console.print(f"  kubectl get pods -n {namespace}")
        console.print(f"  helm status {release_name} -n {namespace}")

    except (DeploymentError, HelmError) as e:
        console.print(f"[red]Deployment failed:[/red] {str(e)}")
        logger.exception("Deployment failed")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}")
        logger.exception("Unexpected error during deployment")
        raise typer.Exit(1) from e
