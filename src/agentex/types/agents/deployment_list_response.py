# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime
from typing_extensions import Literal, TypeAlias

from ..._models import BaseModel

__all__ = ["DeploymentListResponse", "DeploymentListResponseItem"]


class DeploymentListResponseItem(BaseModel):
    id: str
    """The unique identifier of the deployment."""

    agent_id: str
    """The agent this deployment belongs to."""

    docker_image: str
    """Full Docker image URI."""

    is_production: bool
    """Whether this is the production deployment."""

    status: Literal["Pending", "Ready", "Failed"]
    """Current deployment status."""

    acp_url: Optional[str] = None
    """ACP URL set when agent registers."""

    created_at: Optional[datetime] = None
    """When the deployment was created."""

    expires_at: Optional[datetime] = None
    """When marked for cleanup."""

    helm_release_name: Optional[str] = None
    """Helm release name for cleanup."""

    promoted_at: Optional[datetime] = None
    """When promoted to production."""

    registration_metadata: Optional[Dict[str, object]] = None
    """Git/build metadata from the agent pod."""

    sgp_deploy_id: Optional[str] = None
    """Correlates to SGP's agentex_deploys.id."""


DeploymentListResponse: TypeAlias = List[DeploymentListResponseItem]
