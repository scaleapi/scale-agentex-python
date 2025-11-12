from __future__ import annotations

from pydantic import Field, BaseModel, validator, model_validator


class TemporalWorkflowConfig(BaseModel):
    """
    Configuration for the temporal workflow that defines the agent.

    Attributes:
        name: The name of the temporal workflow that defines the agent.
        queue_name: The name of the temporal queue to send tasks to.
    """

    name: str = Field(
        ..., description="The name of the temporal workflow that defines the agent."
    )
    queue_name: str = Field(
        ..., description="The name of the temporal queue to send tasks to."
    )


# TODO: Remove this class when we remove the agentex agents create
class TemporalWorkerConfig(BaseModel):
    """
    Configuration for temporal worker deployment

    Attributes:
        image: The image to use for the temporal worker
        workflow: The temporal workflow configuration
    """

    image: str | None = Field(
        default=None, description="Image to use for the temporal worker"
    )
    workflow: TemporalWorkflowConfig | None = Field(
        default=None,
        description="Configuration for the temporal workflow that defines the agent. Only required for agents that leverage Temporal.",
    )


class TemporalConfig(BaseModel):
    """
    Simplified temporal configuration for agents

    Attributes:
        enabled: Whether this agent uses Temporal workflows
        workflow: The temporal workflow configuration
        workflows: The list of temporal workflow configurations
        health_check_port: Port for temporal worker health check endpoint
    """

    enabled: bool = Field(
        default=False, description="Whether this agent uses Temporal workflows"
    )
    workflow: TemporalWorkflowConfig | None = Field(
        default=None,
        description="Temporal workflow configuration. Required when enabled=True. (deprecated: use workflows instead)",
    )
    workflows: list[TemporalWorkflowConfig] | None = Field(
        default=None,
        description="List of temporal workflow configurations. Used when enabled=true.",
    )
    health_check_port: int | None = Field(
        default=None,
        description="Port for temporal worker health check endpoint. Defaults to 80 if not specified.",
    )

    @validator("workflows")
    def validate_workflows_not_empty(cls, v):
        """Ensure workflows list is not empty when provided"""
        if v is not None and len(v) == 0:
            raise ValueError("workflows list cannot be empty when provided")
        return v

    @model_validator(mode="after")
    def validate_temporal_config_when_enabled(self):
        """Validate that workflow configuration exists when enabled=true"""
        if self.enabled:
            # Must have either workflow (legacy) or workflows (new)
            if not self.workflow and (not self.workflows or len(self.workflows) == 0):
                raise ValueError(
                    "When temporal.enabled=true, either 'workflow' or 'workflows' must be provided and non-empty"
                )

        return self
