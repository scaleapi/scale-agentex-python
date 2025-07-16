# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

from .acp_type import AcpType

__all__ = ["AgentRegisterParams"]


class AgentRegisterParams(TypedDict, total=False):
    acp_type: Required[AcpType]
    """The type of ACP to use for the agent."""

    acp_url: Required[str]
    """The URL of the ACP server for the agent."""

    description: Required[str]
    """The description of the agent."""

    name: Required[str]
    """The unique name of the agent."""

    agent_id: Optional[str]
    """Optional agent ID if the agent already exists and needs to be updated."""
