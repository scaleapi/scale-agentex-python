# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Literal, Required, TypedDict

__all__ = ["AgentRegisterBuildParams"]


class AgentRegisterBuildParams(TypedDict, total=False):
    description: Required[str]
    """The description of the agent."""

    name: Required[str]
    """The unique name of the agent."""

    agent_input_type: Optional[Literal["text", "json"]]
    """The type of input the agent expects."""

    principal_context: object
    """Principal used for authorization"""

    registration_metadata: Optional[Dict[str, object]]
    """The metadata for the agent's build registration."""
