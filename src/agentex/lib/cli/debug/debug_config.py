"""
Debug configuration models for AgentEx CLI debugging.
"""

import socket
from enum import Enum
from typing import Optional

from agentex.lib.utils.model_utils import BaseModel


class DebugMode(str, Enum):
    """Debug mode options"""
    WORKER = "worker"
    ACP = "acp"
    BOTH = "both"
    NONE = "none"


class DebugConfig(BaseModel):
    """Configuration for debug mode"""
    
    enabled: bool = False
    mode: DebugMode = DebugMode.NONE
    port: int = 5678
    wait_for_attach: bool = False
    auto_port: bool = True  # Automatically find available port if specified port is busy
    
    @classmethod
    def create_worker_debug(
        cls, 
        port: int = 5678, 
        wait_for_attach: bool = False,
        auto_port: bool = True
    ) -> "DebugConfig":
        """Create debug config for worker debugging"""
        return cls(
            enabled=True,
            mode=DebugMode.WORKER,
            port=port,
            wait_for_attach=wait_for_attach,
            auto_port=auto_port
        )
    
    @classmethod
    def create_acp_debug(
        cls, 
        port: int = 5679, 
        wait_for_attach: bool = False,
        auto_port: bool = True
    ) -> "DebugConfig":
        """Create debug config for ACP debugging"""
        return cls(
            enabled=True,
            mode=DebugMode.ACP,
            port=port,
            wait_for_attach=wait_for_attach,
            auto_port=auto_port
        )
    
    @classmethod
    def create_both_debug(
        cls, 
        worker_port: int = 5678,
        acp_port: int = 5679,
        wait_for_attach: bool = False,
        auto_port: bool = True
    ) -> "DebugConfig":
        """Create debug config for both worker and ACP debugging"""
        return cls(
            enabled=True,
            mode=DebugMode.BOTH,
            port=worker_port,  # Primary port for worker
            wait_for_attach=wait_for_attach,
            auto_port=auto_port
        )
    
    def should_debug_worker(self) -> bool:
        """Check if worker should be debugged"""
        return self.enabled and self.mode in (DebugMode.WORKER, DebugMode.BOTH)
    
    def should_debug_acp(self) -> bool:
        """Check if ACP should be debugged"""
        return self.enabled and self.mode in (DebugMode.ACP, DebugMode.BOTH)
    
    def get_worker_port(self) -> int:
        """Get port for worker debugging"""
        return self.port
    
    def get_acp_port(self) -> int:
        """Get port for ACP debugging"""
        if self.mode == DebugMode.BOTH:
            return self.port + 1  # Use port + 1 for ACP when debugging both
        return self.port


def find_available_port(start_port: int = 5678, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    
    # If we can't find an available port, just return the start port
    # and let the debug server handle the error
    return start_port


def resolve_debug_port(config: DebugConfig, target_port: int) -> int:
    """Resolve the actual port to use for debugging"""
    if config.auto_port:
        return find_available_port(target_port)
    return target_port 