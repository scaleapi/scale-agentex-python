"""
Debug process handlers for AgentEx CLI.

Provides debug-enabled versions of ACP server and temporal worker startup.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    import asyncio.subprocess

from .debug_config import DebugConfig, resolve_debug_port
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)
console = Console()


async def start_temporal_worker_debug(
    worker_path: Path, 
    env: Dict[str, str], 
    debug_config: DebugConfig
):
    """Start temporal worker with debug support"""
    
    if not debug_config.should_debug_worker():
        raise ValueError("Debug config is not configured for worker debugging")
    
    # Resolve the actual debug port
    debug_port = resolve_debug_port(debug_config, debug_config.get_worker_port())
    
    # Add debug environment variables
    debug_env = env.copy()
    debug_env.update({
        "AGENTEX_DEBUG_ENABLED": "true",
        "AGENTEX_DEBUG_PORT": str(debug_port),
        "AGENTEX_DEBUG_WAIT_FOR_ATTACH": str(debug_config.wait_for_attach).lower(),
        "AGENTEX_DEBUG_TYPE": "worker"
    })
    
    # Start the worker process
    # For debugging, use absolute path to run_worker.py to run from workspace root
    worker_script = worker_path.parent / "run_worker.py"
    cmd = [sys.executable, str(worker_script)]
    
    console.print(f"[blue]🐛 Starting Temporal worker in debug mode[/blue]")
    console.print(f"[yellow]📡 Debug server will listen on port {debug_port}[/yellow]")
    console.print(f"[green]✓ VS Code should connect to: localhost:{debug_port}[/green]")
    
    if debug_config.wait_for_attach:
        console.print(f"[yellow]⏳ Worker will wait for debugger to attach[/yellow]")
    
    console.print(f"[dim]💡 In your IDE: Attach to localhost:{debug_port}[/dim]")
    console.print(f"[dim]🔧 If connection fails, check that VS Code launch.json uses port {debug_port}[/dim]")
    
    return await asyncio.create_subprocess_exec(
        *cmd,
        cwd=Path.cwd(),  # Run from current working directory (workspace root)
        env=debug_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )


async def start_acp_server_debug(
    acp_path: Path, 
    port: int, 
    env: Dict[str, str],
    debug_config: DebugConfig
):
    """Start ACP server with debug support"""
    
    if not debug_config.should_debug_acp():
        raise ValueError("Debug config is not configured for ACP debugging")
    
    # Resolve the actual debug port
    debug_port = resolve_debug_port(debug_config, debug_config.get_acp_port())
    
    # Add debug environment variables
    debug_env = env.copy()
    debug_env.update({
        "AGENTEX_DEBUG_ENABLED": "true",
        "AGENTEX_DEBUG_PORT": str(debug_port),
        "AGENTEX_DEBUG_WAIT_FOR_ATTACH": str(debug_config.wait_for_attach).lower(),
        "AGENTEX_DEBUG_TYPE": "acp"
    })
    
    # Disable uvicorn auto-reload in debug mode to prevent conflicts
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        f"{acp_path.parent.name}.acp:acp",
        "--port",
        str(port),
        "--host",
        "0.0.0.0",
        # Note: No --reload flag when debugging
    ]

    console.print(f"[blue]🐛 Starting ACP server in debug mode[/blue]")
    console.print(f"[yellow]📡 Debug server will listen on port {debug_port}[/yellow]")
    
    if debug_config.wait_for_attach:
        console.print(f"[yellow]⏳ ACP server will wait for debugger to attach[/yellow]")
        
    console.print(f"[dim]💡 In your IDE: Attach to localhost:{debug_port}[/dim]")

    return await asyncio.create_subprocess_exec(
        *cmd,
        cwd=acp_path.parent.parent,
        env=debug_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )


def create_debug_startup_script() -> str:
    """Create a Python script snippet for debug initialization"""
    return '''
import os
import sys

# Debug initialization for AgentEx
if os.getenv("AGENTEX_DEBUG_ENABLED") == "true":
    try:
        import debugpy
        debug_port = int(os.getenv("AGENTEX_DEBUG_PORT", "5678"))
        debug_type = os.getenv("AGENTEX_DEBUG_TYPE", "unknown")
        wait_for_attach = os.getenv("AGENTEX_DEBUG_WAIT_FOR_ATTACH", "false").lower() == "true"
        
        # Configure debugpy
        debugpy.configure(subProcess=False)
        debugpy.listen(debug_port)
        
        print(f"🐛 [{debug_type.upper()}] Debug server listening on port {debug_port}")
        
        if wait_for_attach:
            print(f"⏳ [{debug_type.upper()}] Waiting for debugger to attach...")
            debugpy.wait_for_client()
            print(f"✅ [{debug_type.upper()}] Debugger attached!")
        else:
            print(f"📡 [{debug_type.upper()}] Ready for debugger attachment")
            
    except ImportError:
        print("❌ debugpy not available. Install with: pip install debugpy")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Debug setup failed: {e}")
        sys.exit(1)
'''


def inject_debug_code_to_worker_template() -> str:
    """Generate debug code to inject into worker template"""
    return """
# === DEBUG SETUP (Auto-generated by AgentEx CLI) ===
""" + create_debug_startup_script() + """
# === END DEBUG SETUP ===
"""


def inject_debug_code_to_acp_template() -> str:
    """Generate debug code to inject into ACP template"""
    return """
# === DEBUG SETUP (Auto-generated by AgentEx CLI) ===
""" + create_debug_startup_script() + """
# === END DEBUG SETUP ===
""" 