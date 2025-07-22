from typing import Any, Literal

from pydantic import Field

from agentex.lib.types.agent_configs import TemporalConfig, TemporalWorkflowConfig
from agentex.lib.types.credentials import CredentialMapping
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel

logger = make_logger(__name__)


class AgentConfig(BaseModel):
    name: str = Field(
        ...,
        description="The name of the agent.",
        pattern=r"^[a-z0-9-]+$",
    )
    acp_type: Literal["sync", "agentic"] = Field(..., description="The type of agent.")
    description: str = Field(..., description="The description of the agent.")
    env: dict[str, str] | None = Field(
        default=None, description="Environment variables to set directly in the agent deployment"
    )
    credentials: list[CredentialMapping | dict[str, Any]] | None = Field(
        default=None,
        description="List of credential mappings to mount to the agent deployment. Supports both legacy format and new typed credentials.",
    )
    temporal: TemporalConfig | None = Field(
        default=None, description="Temporal workflow configuration for this agent"
    )

    def is_temporal_agent(self) -> bool:
        """Check if this agent uses Temporal workflows"""
        # Check temporal config with enabled flag
        if self.temporal and self.temporal.enabled:
            return True
        return False

    def get_temporal_workflow_config(self) -> TemporalWorkflowConfig | None:
        """Get temporal workflow configuration, checking both new and legacy formats"""
        # Check new workflows list first
        if self.temporal and self.temporal.enabled and self.temporal.workflows:
            return self.temporal.workflows[0]  # Return first workflow for backward compatibility

        # Check legacy single workflow
        if self.temporal and self.temporal.enabled and self.temporal.workflow:
            return self.temporal.workflow

        return None

    def get_temporal_workflows(self) -> list[TemporalWorkflowConfig]:
        """Get all temporal workflow configurations"""
        # Check new workflows list first
        if self.temporal and self.temporal.enabled and self.temporal.workflows:
            return self.temporal.workflows

        # Check legacy single workflow
        if self.temporal and self.temporal.enabled and self.temporal.workflow:
            return [self.temporal.workflow]

        return []
