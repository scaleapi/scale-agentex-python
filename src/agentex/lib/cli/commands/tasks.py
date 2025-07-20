import typer
from rich import print_json
from rich.console import Console

from agentex import Agentex
from agentex.lib.cli.handlers.cleanup_handlers import cleanup_agent_workflows
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)
console = Console()

tasks = typer.Typer()


@tasks.command()
def get(
    task_id: str = typer.Argument(..., help="ID of the task to get"),
):
    """
    Get the task with the given ID.
    """
    logger.info(f"Getting task: {task_id}")
    client = Agentex()
    task = client.tasks.retrieve(task_id=task_id)
    print(f"Full Task {task_id}:")
    print_json(data=task.to_dict())


@tasks.command()
def list():
    """
    List all tasks.
    """
    client = Agentex()
    tasks = client.tasks.list()
    print_json(data=[task.to_dict() for task in tasks])


@tasks.command()
def list_running(
    agent_name: str = typer.Option(..., help="Name of the agent to list running tasks for"),
):
    """
    List all currently running tasks for a specific agent.
    """
    client = Agentex()
    all_tasks = client.tasks.list()
    running_tasks = [task for task in all_tasks if hasattr(task, 'status') and task.status == "RUNNING"]
    
    if not running_tasks:
        console.print(f"[yellow]No running tasks found for agent '{agent_name}'[/yellow]")
        return
        
    console.print(f"[green]Found {len(running_tasks)} running task(s) for agent '{agent_name}':[/green]")
    
    # Convert to dict with proper datetime serialization
    serializable_tasks = []
    for task in running_tasks:
        try:
            # Use model_dump with mode='json' for proper datetime handling
            if hasattr(task, 'model_dump'):
                serializable_tasks.append(task.model_dump(mode='json'))
            else:
                # Fallback for non-Pydantic objects
                serializable_tasks.append({
                    "id": getattr(task, 'id', 'unknown'), 
                    "status": getattr(task, 'status', 'unknown')
                })
        except Exception as e:
            logger.warning(f"Failed to serialize task: {e}")
            # Minimal fallback
            serializable_tasks.append({
                "id": getattr(task, 'id', 'unknown'), 
                "status": getattr(task, 'status', 'unknown')
            })
    
    print_json(data=serializable_tasks)


@tasks.command()
def delete(
    task_id: str = typer.Argument(..., help="ID of the task to delete"),
):
    """
    Delete the task with the given ID.
    """
    logger.info(f"Deleting task: {task_id}")
    client = Agentex()
    client.tasks.delete(task_id=task_id)
    logger.info(f"Task deleted: {task_id}")


@tasks.command()
def cleanup(
    agent_name: str = typer.Option(..., help="Name of the agent to cleanup tasks for"),
    force: bool = typer.Option(False, help="Force cleanup using direct Temporal termination (bypasses development check)"),
):
    """
    Clean up all running tasks/workflows for an agent.
    
    By default, uses graceful cancellation via agent RPC.
    With --force, directly terminates workflows via Temporal client.
    """
    try:
        console.print(f"[blue]Starting cleanup for agent '{agent_name}'...[/blue]")
        
        cleanup_agent_workflows(
            agent_name=agent_name,
            force=force,
            development_only=True
        )
        
        console.print(f"[green]✓ Cleanup completed for agent '{agent_name}'[/green]")
        
    except Exception as e:
        console.print(f"[red]Cleanup failed: {str(e)}[/red]")
        logger.exception("Task cleanup failed")
        raise typer.Exit(1) from e
