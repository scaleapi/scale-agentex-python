import inspect
import json
import os
from pathlib import Path

from typing import Literal
from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer
from agentex.lib.sdk.fastacp.impl.agentic_base_acp import AgenticBaseACP
from agentex.lib.sdk.fastacp.impl.sync_acp import SyncACP
from agentex.lib.sdk.fastacp.impl.temporal_acp import TemporalACP
from agentex.lib.types.fastacp import (
    AgenticACPConfig,
    BaseACPConfig,
    SyncACPConfig,
)
from agentex.lib.utils.logging import make_logger

# Add new mappings between ACP types and configs here
# Add new mappings between ACP types and implementations here
AGENTIC_ACP_IMPLEMENTATIONS: dict[Literal["temporal", "base"], type[BaseACPServer]] = {
    "temporal": TemporalACP,
    "base": AgenticBaseACP,
}

logger = make_logger(__name__)

class FastACP:
    """Factory for creating FastACP instances

    Supports two main ACP types:
    - "sync": Simple synchronous ACP implementation
    - "agentic": Advanced ACP with sub-types "base" or "temporal" (requires config)
    """

    @staticmethod
    # Note: the config is optional and not used right now but is there to be extended in the future
    def create_sync_acp(config: SyncACPConfig | None = None, **kwargs) -> SyncACP:
        """Create a SyncACP instance"""
        return SyncACP.create(**kwargs)

    @staticmethod
    def create_agentic_acp(config: AgenticACPConfig, **kwargs) -> BaseACPServer:
        """Create an agentic ACP instance (base or temporal)

        Args:
            config: AgenticACPConfig with type="base" or type="temporal"
            **kwargs: Additional configuration parameters
        """
        # Get implementation class
        implementation_class = AGENTIC_ACP_IMPLEMENTATIONS[config.type]
        # Handle temporal-specific configuration
        if config.type == "temporal":
            # Extract temporal_address from config if it's a TemporalACPConfig
            temporal_config = kwargs.copy()
            if hasattr(config, "temporal_address"):
                temporal_config["temporal_address"] = config.temporal_address
            return implementation_class.create(**temporal_config)
        else:
            return implementation_class.create(**kwargs)

    @staticmethod
    def maybe_get_build_info() -> None:
        """If a build-info.json file is present, load it and set the AGENT_COMMIT and AGENT_CODE_URL environment variables"""
        acp_root = Path(inspect.stack()[1].filename).resolve().parents[0]
        build_info_path = acp_root / "build-info.json"
        if build_info_path.exists():
            try:
                with open(build_info_path, "r") as f:
                    build_info = json.load(f)
                    if build_info.get("agent_commit"):
                        os.environ["AGENT_COMMIT"] = build_info.get("agent_commit")
                    if build_info.get("agent_repo") and build_info.get("agent_path"):
                        os.environ["AGENT_CODE_URL"] = build_info.get("agent_repo") + "/" + build_info.get("agent_path")
            except Exception as e:
                logger.error(f"Error loading build info: {e}")

    @staticmethod
    def create(
        acp_type: Literal["sync", "agentic"], config: BaseACPConfig | None = None, **kwargs
    ) -> BaseACPServer | SyncACP | AgenticBaseACP | TemporalACP:
        """Main factory method to create any ACP type

        Args:
            acp_type: Type of ACP to create ("sync" or "agentic")
            config: Configuration object. Required for agentic type.
            **kwargs: Additional configuration parameters
        """ 

        FastACP.maybe_get_build_info()
        
        if acp_type == "sync":
            sync_config = config if isinstance(config, SyncACPConfig) else None
            return FastACP.create_sync_acp(sync_config, **kwargs)
        elif acp_type == "agentic":
            if config is None:
                config = AgenticACPConfig(type="base")
            if not isinstance(config, AgenticACPConfig):
                raise ValueError("AgenticACPConfig is required for agentic ACP type")
            return FastACP.create_agentic_acp(config, **kwargs)
