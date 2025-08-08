"""
Debug utilities for AgentEx development.

Provides debugging setup functionality that can be used across different components.
"""

import os
import debugpy  # type: ignore


def setup_debug_if_enabled() -> None:
    """
    Setup debugpy if debug mode is enabled via environment variables.
    
    This function checks for AgentEx debug environment variables and configures
    debugpy accordingly. It's designed to be called early in worker startup.
    
    Environment Variables:
        AGENTEX_DEBUG_ENABLED: Set to "true" to enable debug mode
        AGENTEX_DEBUG_PORT: Port for debug server (default: 5678)
        AGENTEX_DEBUG_TYPE: Type identifier for logging (default: "worker")
        AGENTEX_DEBUG_WAIT_FOR_ATTACH: Set to "true" to wait for debugger attachment
    
    Raises:
        Any exception from debugpy setup (will bubble up naturally)
    """
    if os.getenv("AGENTEX_DEBUG_ENABLED") == "true":
        debug_port = int(os.getenv("AGENTEX_DEBUG_PORT", "5678"))
        debug_type = os.getenv("AGENTEX_DEBUG_TYPE", "worker")
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


def is_debug_enabled() -> bool:
    """
    Check if debug mode is currently enabled.
    
    Returns:
        bool: True if AGENTEX_DEBUG_ENABLED is set to "true"
    """
    return os.getenv("AGENTEX_DEBUG_ENABLED", "false").lower() == "true"


def get_debug_port() -> int:
    """
    Get the debug port from environment variables.
    
    Returns:
        int: Debug port (default: 5678)
    """
    return int(os.getenv("AGENTEX_DEBUG_PORT", "5678"))
