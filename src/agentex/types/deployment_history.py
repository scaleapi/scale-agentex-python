# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from datetime import datetime

from .._models import BaseModel

__all__ = ["DeploymentHistory"]


class DeploymentHistory(BaseModel):
    id: str
    """The unique identifier of the deployment record"""

    agent_id: str
    """The ID of the agent this deployment belongs to"""

    author_email: str
    """Email of the commit author"""

    author_name: str
    """Name of the commit author"""

    branch_name: str
    """Name of the branch"""

    build_timestamp: datetime
    """When the build was created"""

    commit_hash: str
    """Git commit hash for this deployment"""

    deployment_timestamp: datetime
    """When this deployment was first seen in the system"""
