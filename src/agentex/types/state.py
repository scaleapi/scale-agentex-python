# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["State"]


class State(BaseModel):
    """Represents a state in the agent system.

    A state is associated uniquely with a task and an agent.

    This entity is used to store states in MongoDB, with each state
    associated with a specific task and agent. The combination of task_id and agent_id is globally unique.

    The state is a dictionary of arbitrary data.
    """

    id: str
    """The task state's unique id"""

    agent_id: str

    created_at: datetime
    """The timestamp when the state was created"""

    state: Dict[str, object]

    task_id: str

    updated_at: Optional[datetime] = None
    """The timestamp when the state was last updated"""
