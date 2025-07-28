import asyncio
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from agentex.lib.cli.utils.auth_utils import _encode_principal_context
from agentex.lib.cli.handlers.cleanup_handlers import (
    cleanup_agent_workflows,
    should_cleanup_on_restart
)
from agentex.lib.cli.utils.path_utils import (
    get_file_paths,
    calculate_uvicorn_target_for_local,
)

from agentex.lib.environment_variables import EnvVarKeys
from agentex.lib.sdk.config.agent_manifest import AgentManifest

# Import debug functionality
from agentex.lib.cli.debug import DebugConfig, start_acp_server_debug, start_temporal_worker_debug
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)
console = Console()


class RunError(Exception):
    """An error occurred during agent run"""


class ProcessManager:
    """Manages multiple subprocesses with proper cleanup"""

    def __init__(self):
        self.processes: list[asyncio.subprocess.Process] = []
        self.shutdown_event = asyncio.Event()

    def add_process(self, process: asyncio.subprocess.Process):
        """Add a process to be managed"""
        self.processes.append(process)

    async def wait_for_shutdown(self):
        """Wait for shutdown signal"""
        await self.shutdown_event.wait()

    def shutdown(self):
        """Signal shutdown and terminate all processes"""
        self.shutdown_event.set()

    async def cleanup_processes(self):
        """Clean up all processes"""
        if not self.processes:
            return

        console.print("\n[yellow]Shutting down processes...[/yellow]")

        # Send SIGTERM to all processes
        for process in self.processes:
            if process.returncode is None:  # Process is still running
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass  # Process already terminated

        # Wait for graceful shutdown with shorter timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*[p.wait() for p in self.processes], return_exceptions=True),
                timeout=2.0,  # Reduced from 5.0 seconds
            )
        except TimeoutError:
            # Force kill if not terminated gracefully
            console.print("[yellow]Force killing unresponsive processes...[/yellow]")
            for process in self.processes:
                if process.returncode is None:
                    try:
                        process.kill()
                        await asyncio.wait_for(process.wait(), timeout=1.0)
                    except (ProcessLookupError, TimeoutError):
                        pass  # Process already dead or kill failed

        console.print("[green]All processes stopped[/green]")


async def start_temporal_worker_with_reload(
    worker_path: Path, env: dict[str, str], process_manager: ProcessManager
) -> asyncio.Task[None]:
    """Start temporal worker with auto-reload using watchfiles"""
    
    try:
        from watchfiles import awatch
    except ImportError:
        console.print("[yellow]watchfiles not installed, falling back to basic worker start[/yellow]")
        console.print("[dim]Install with: pip install watchfiles[/dim]")
        # Fallback to regular worker without reload
        worker_process = await start_temporal_worker(worker_path, env)
        process_manager.add_process(worker_process)
        return asyncio.create_task(stream_process_output(worker_process, "WORKER"))
    
    async def worker_runner() -> None:
        current_process: asyncio.subprocess.Process | None = None
        output_task: asyncio.Task[None] | None = None
        
        console.print(f"[blue]Starting Temporal worker with auto-reload from {worker_path}...[/blue]")
        
        async def start_worker() -> asyncio.subprocess.Process:
            nonlocal current_process, output_task
            
            # PRE-RESTART CLEANUP - NEW!
            if current_process is not None:
                # Extract agent name from worker path for cleanup

                agent_name = env.get("AGENT_NAME")
                if agent_name is None:
                    agent_name = worker_path.parent.parent.name
                
                # Perform cleanup if configured
                if should_cleanup_on_restart():
                    console.print("[yellow]Cleaning up workflows before worker restart...[/yellow]")
                    try:
                        cleanup_agent_workflows(agent_name)
                    except Exception as e:
                        logger.warning(f"Cleanup failed: {e}")
                        console.print(f"[yellow]⚠ Cleanup failed: {str(e)}[/yellow]")
            
            # Clean up previous process
            if current_process and current_process.returncode is None:
                current_process.terminate()
                try:
                    await asyncio.wait_for(current_process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    current_process.kill()
                    await current_process.wait()
            
            # Cancel previous output task
            if output_task:
                output_task.cancel()
                try:
                    await output_task
                except asyncio.CancelledError:
                    pass
            
            current_process = await start_temporal_worker(worker_path, env)
            process_manager.add_process(current_process)
            console.print("[green]Temporal worker started[/green]")
            return current_process
        
        try:
            # Start initial worker
            await start_worker()
            if current_process:
                output_task = asyncio.create_task(stream_process_output(current_process, "WORKER"))
            
            # Watch for file changes
            async for changes in awatch(worker_path.parent):
                # Filter for Python files
                py_changes = [(change, path) for change, path in changes if str(path).endswith('.py')]
                
                if py_changes:
                    changed_files = [str(Path(path).relative_to(worker_path.parent)) for _, path in py_changes]
                    console.print(f"[yellow]File changes detected: {changed_files}[/yellow]")
                    console.print("[yellow]Restarting Temporal worker...[/yellow]")
                    
                    # Restart worker (with cleanup handled in start_worker)
                    await start_worker()
                    if current_process:
                        output_task = asyncio.create_task(stream_process_output(current_process, "WORKER"))
                    
        except asyncio.CancelledError:
            # Clean shutdown
            if output_task:
                output_task.cancel()
                try:
                    await output_task
                except asyncio.CancelledError:
                    pass
            
            if current_process and current_process.returncode is None:
                current_process.terminate()
                try:
                    await asyncio.wait_for(current_process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    current_process.kill()
                    await current_process.wait()
            raise
    
    return asyncio.create_task(worker_runner())


async def start_acp_server(
    acp_path: Path, port: int, env: dict[str, str], manifest_dir: Path
) -> asyncio.subprocess.Process:
    """Start the ACP server process"""
    # Use file path relative to manifest directory if possible
    uvicorn_target = calculate_uvicorn_target_for_local(acp_path, manifest_dir)
    
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        f"{uvicorn_target}:acp",
        "--reload",
        "--reload-dir",
        str(acp_path.parent),  # Watch the project directory specifically
        "--port",
        str(port),
        "--host",
        "0.0.0.0",
    ]

    console.print(f"[blue]Starting ACP server from {acp_path} on port {port}...[/blue]")
    return await asyncio.create_subprocess_exec(
        *cmd,
        cwd=manifest_dir,  # Always use manifest directory as CWD for consistency
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )


async def start_temporal_worker(
    worker_path: Path, env: dict[str, str]
) -> asyncio.subprocess.Process:
    """Start the temporal worker process"""
    cmd = [sys.executable, "-m", "run_worker"]

    console.print(f"[blue]Starting Temporal worker from {worker_path}...[/blue]")

    return await asyncio.create_subprocess_exec(
        *cmd,
        cwd=worker_path.parent,  # Use worker directory as CWD for imports to work
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )


async def stream_process_output(process: asyncio.subprocess.Process, prefix: str):
    """Stream process output with prefix"""
    try:
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            decoded_line = line.decode("utf-8").rstrip()
            if decoded_line:  # Only print non-empty lines
                console.print(f"[dim]{prefix}:[/dim] {decoded_line}")
    except Exception as e:
        logger.debug(f"Output streaming ended for {prefix}: {e}")


async def run_agent(manifest_path: str, debug_config: "DebugConfig | None" = None):
    """Run an agent locally from the given manifest"""

    # Validate manifest exists
    manifest_file = Path(manifest_path)

    if not manifest_file.exists():
        raise RunError(f"Manifest file not found: {manifest_path}")

    # Parse manifest
    try:
        manifest = AgentManifest.from_yaml(file_path=manifest_path)
    except Exception as e:
        raise RunError(f"Failed to parse manifest: {str(e)}") from e

    # Get and validate file paths
    try:
        file_paths = get_file_paths(manifest, manifest_path)
    except Exception as e:
        raise RunError(str(e)) from e

    # Check if temporal agent and validate worker file
    if is_temporal_agent(manifest):
        if not file_paths["worker"]:
            raise RunError("Temporal agent requires a worker file path to be configured")

    # Create environment for subprocesses
    agent_env = create_agent_environment(manifest)

    # Setup process manager
    process_manager = ProcessManager()

    try:
        console.print(
            Panel.fit(
                f"🚀 [bold blue]Running Agent: {manifest.agent.name}[/bold blue]",
                border_style="blue",
            )
        )

        # Start ACP server (with debug support if enabled)
        manifest_dir = Path(manifest_path).parent
        if debug_config and debug_config.should_debug_acp():
            acp_process = await start_acp_server_debug(
                file_paths["acp"], manifest.local_development.agent.port, agent_env, debug_config
            )
        else:
            acp_process = await start_acp_server(
                file_paths["acp"], manifest.local_development.agent.port, agent_env, manifest_dir
            )
        process_manager.add_process(acp_process)

        # Start output streaming for ACP
        acp_output_task = asyncio.create_task(stream_process_output(acp_process, "ACP"))

        tasks = [acp_output_task]

        # Start temporal worker if needed (with debug support if enabled)
        if is_temporal_agent(manifest) and file_paths["worker"]:
            if debug_config and debug_config.should_debug_worker():
                # In debug mode, start worker without auto-reload to prevent conflicts
                worker_process = await start_temporal_worker_debug(
                    file_paths["worker"], agent_env, debug_config
                )
                process_manager.add_process(worker_process)
                worker_task = asyncio.create_task(stream_process_output(worker_process, "WORKER"))
            else:
                # Normal mode with auto-reload
                worker_task = await start_temporal_worker_with_reload(file_paths["worker"], agent_env, process_manager)
            tasks.append(worker_task)

        console.print(
            f"\n[green]✓ Agent running at: http://localhost:{manifest.local_development.agent.port}[/green]"
        )
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        # Wait for shutdown signal or process failure
        try:
            await process_manager.wait_for_shutdown()
        except KeyboardInterrupt:
            console.print("\n[yellow]Received shutdown signal...[/yellow]")
        
        # Cancel output streaming tasks
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.exception("Error running agent")
        raise RunError(f"Failed to run agent: {str(e)}") from e

    finally:
        # Ensure cleanup happens
        await process_manager.cleanup_processes()





def create_agent_environment(manifest: AgentManifest) -> dict[str, str]:
    """Create environment variables for agent processes without modifying os.environ"""
    # Start with current environment
    env = dict(os.environ)

    agent_config = manifest.agent

    # TODO: Combine this logic with the deploy_handlers so that we can reuse the env vars
    env_vars = {
        "ENVIRONMENT": "development",
        "TEMPORAL_ADDRESS": "localhost:7233",
        "REDIS_URL": "redis://localhost:6379",
        "AGENT_NAME": manifest.agent.name,
        "ACP_TYPE": manifest.agent.acp_type,
        "ACP_URL": f"http://{manifest.local_development.agent.host_address}",
        "ACP_PORT": str(manifest.local_development.agent.port),
    }

    # Add authorization principal if set
    encoded_principal = _encode_principal_context(manifest)
    if encoded_principal:
        env_vars[EnvVarKeys.AUTH_PRINCIPAL_B64] = encoded_principal

    # Add description if available
    if manifest.agent.description:
        env_vars["AGENT_DESCRIPTION"] = manifest.agent.description

    # Add temporal-specific variables if this is a temporal agent
    if manifest.agent.is_temporal_agent():
        temporal_config = manifest.agent.get_temporal_workflow_config()
        if temporal_config:
            env_vars["WORKFLOW_NAME"] = temporal_config.name
            env_vars["WORKFLOW_TASK_QUEUE"] = temporal_config.queue_name

    if agent_config.env:
        for key, value in agent_config.env.items():
            env_vars[key] = value

    env.update(env_vars)

    return env


def is_temporal_agent(manifest: AgentManifest) -> bool:
    """Check if this is a temporal agent"""
    return manifest.agent.is_temporal_agent()
