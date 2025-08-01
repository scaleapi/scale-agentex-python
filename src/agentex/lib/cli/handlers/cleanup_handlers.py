import asyncio
import os

from rich.console import Console

from agentex import Agentex
from agentex.lib.utils.logging import make_logger

# Import Temporal client for direct workflow termination
try:
    from temporalio.client import Client as TemporalClient  # type: ignore
except ImportError:
    TemporalClient = None

logger = make_logger(__name__)
console = Console()


def should_cleanup_on_restart() -> bool:
    """
    Check if cleanup should be performed on restart.
    
    Returns True if:
    - ENVIRONMENT=development, OR
    - AUTO_CLEANUP_ON_RESTART=true
    """
    env = os.getenv("ENVIRONMENT", "").lower()
    auto_cleanup = os.getenv("AUTO_CLEANUP_ON_RESTART", "true").lower()
    
    return env == "development" or auto_cleanup == "true"


def cleanup_agent_workflows(
    agent_name: str,
    force: bool = False,
    development_only: bool = True
) -> None:
    """
    Clean up all running workflows for an agent during development.
    
    This cancels (graceful) all running tasks for the specified agent.
    When force=True, directly terminates workflows via Temporal client.
    
    Args:
        agent_name: Name of the agent to cleanup workflows for
        force: If True, directly terminate workflows via Temporal client
        development_only: Only perform cleanup in development environment
    """
    
    # Safety check - only run in development mode by default
    if development_only and not force and not should_cleanup_on_restart():
        logger.warning("Cleanup skipped - not in development mode. Use --force to override.")
        return
    
    method = "terminate (direct)" if force else "cancel (via agent)"
    console.print(f"[blue]Cleaning up workflows for agent '{agent_name}' using {method}...[/blue]")
    
    try:
        client = Agentex()
        
        # Get all running tasks
        all_tasks = client.tasks.list()
        running_tasks = [task for task in all_tasks if hasattr(task, 'status') and task.status == "RUNNING"]
        
        if not running_tasks:
            console.print("[yellow]No running tasks found[/yellow]")
            return
        
        console.print(f"[blue]Cleaning up {len(running_tasks)} running task(s) for agent '{agent_name}'...[/blue]")
        
        successful_cleanups = 0
        total_tasks = len(running_tasks)
        
        for task in running_tasks:
            task_cleanup_success = False
            
            if force:
                # Force mode: Do both graceful RPC cancellation AND direct Temporal termination
                rpc_success = False
                temporal_success = False
                
                try:
                    # First: Graceful cancellation via agent RPC (handles database/agent cleanup)
                    cleanup_single_task(client, agent_name, task.id)
                    logger.debug(f"Completed RPC cancellation for task {task.id}")
                    rpc_success = True
                except Exception as e:
                    logger.warning(f"RPC cancellation failed for task {task.id}: {e}")
                
                try:
                    # Second: Direct Temporal termination (ensures workflow is forcefully stopped)
                    asyncio.run(cleanup_single_task_direct(task.id))
                    logger.debug(f"Completed Temporal termination for task {task.id}")
                    temporal_success = True
                except Exception as e:
                    logger.warning(f"Temporal termination failed for task {task.id}: {e}")
                
                # Count as success if either operation succeeded
                task_cleanup_success = rpc_success or temporal_success
                
            else:
                # Normal mode: Only graceful cancellation via agent RPC
                try:
                    cleanup_single_task(client, agent_name, task.id)
                    task_cleanup_success = True
                except Exception as e:
                    logger.error(f"Failed to cleanup task {task.id}: {e}")
                    task_cleanup_success = False
            
            if task_cleanup_success:
                successful_cleanups += 1
                logger.debug(f"Successfully cleaned up task {task.id}")
            else:
                logger.error(f"Failed to cleanup task {task.id}")
                # Don't increment successful_cleanups for actual failures
        
        if successful_cleanups == total_tasks:
            console.print(f"[green]✓ Successfully cleaned up all {successful_cleanups} task(s) for agent '{agent_name}'[/green]")
        elif successful_cleanups > 0:
            console.print(f"[yellow]⚠ Successfully cleaned up {successful_cleanups}/{total_tasks} task(s) for agent '{agent_name}'[/yellow]")
        else:
            console.print(f"[red]✗ Failed to cleanup any tasks for agent '{agent_name}'[/red]")
        
    except Exception as e:
        console.print(f"[red]Agent workflow cleanup failed: {str(e)}[/red]")
        logger.exception("Agent workflow cleanup failed")
        raise


async def cleanup_single_task_direct(task_id: str) -> None:
    """
    Directly terminate a workflow using Temporal client.
    
    Args:
        task_id: ID of the task (used as workflow_id)
    """
    if TemporalClient is None:
        raise ImportError("temporalio package not available for direct workflow termination")
    
    try:
        # Connect to Temporal server (assumes default localhost:7233)
        client = await TemporalClient.connect("localhost:7233")  # type: ignore
        
        # Get workflow handle and terminate
        handle = client.get_workflow_handle(workflow_id=task_id)  # type: ignore
        await handle.terminate()  # type: ignore
        
        logger.debug(f"Successfully terminated workflow {task_id} via Temporal client")
        
    except Exception as e:
        # Check if the workflow was already completed - this is actually a success case
        if "workflow execution already completed" in str(e).lower():
            logger.debug(f"Workflow {task_id} was already completed - no termination needed")
            return  # Don't raise an exception for this case
        
        logger.error(f"Failed to terminate workflow {task_id} via Temporal client: {e}")
        raise


def cleanup_single_task(client: Agentex, agent_name: str, task_id: str) -> None:
    """
    Clean up a single task/workflow using agent RPC cancel method.
    
    Args:
        client: Agentex client instance  
        agent_name: Name of the agent that owns the task
        task_id: ID of the task to cleanup
    """
    try:
        # Use the agent RPC method to cancel the task
        client.agents.rpc_by_name(
            agent_name=agent_name,
            method="task/cancel",
            params={"task_id": task_id}
        )
        logger.debug(f"Successfully cancelled task {task_id} via agent '{agent_name}'")
    
    except Exception as e:
        logger.warning(f"RPC task/cancel failed for task {task_id}: {e}")
        raise