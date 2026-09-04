# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Required, TypedDict

__all__ = ["DeploymentCreateParams"]


class DeploymentCreateParams(TypedDict, total=False):
    docker_image: Required[str]
    """Full Docker image URI."""

    helm_release_name: Optional[str]
    """Helm release name."""

    registration_metadata: Optional[Dict[str, object]]
    """
    Git/build metadata (commit_hash, branch_name, author_name, author_email,
    build_timestamp).
    """

    sgp_deploy_id: Optional[str]
    """SGP deployment ID."""
