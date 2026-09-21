# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

__all__ = ["AgentListParams"]


class AgentListParams(TypedDict, total=False):
    agent_card_metadata: Optional[str]
    """
    JSON-encoded object used to filter agents on
    `registration_metadata.agent_card.metadata` via JSONB containment. Example:
    {"permits_capable": true}. Only matches cards published through the direct
    registration path: registrations that carry a `deployment_id` write the card to
    the deployment record instead of `registration_metadata`, so those agents never
    match this filter.
    """

    limit: int
    """Limit"""

    order_by: Optional[str]
    """Field to order by"""

    order_direction: str
    """Order direction (asc or desc)"""

    page_number: int
    """Page number"""

    task_id: Optional[str]
    """Task ID"""
