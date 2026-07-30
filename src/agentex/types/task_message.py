# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Union, Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel
from .task_message_content import TaskMessageContent

__all__ = ["TaskMessage"]


class TaskMessage(BaseModel):
    """Represents a message in the agent system.

    This entity is used to store messages in MongoDB, with each message
    associated with a specific task.
    """

    content: TaskMessageContent
    """The content of the message.

    This content is not OpenAI compatible. These are messages that are meant to be
    displayed to the user.
    """

    task_id: str
    """ID of the task this message belongs to"""

    # MANUAL PATCH — mirror into the upstream OpenAPI spec (see .stats.yml
    # openapi_spec_url) or the next Stainless regen drops it.
    agent_path: Optional[Union[str, List[str]]] = None
    """Identifier of the agent that emitted this message.

    A single agent id, or a root->emitter path (e.g. ["researcher", "subagent-abc"])
    when nested sub-agents share one task stream. Consumers group/filter events by it.
    """

    id: Optional[str] = None
    """The task message's unique id"""

    created_at: Optional[datetime] = None
    """The timestamp when the message was created"""

    streaming_status: Optional[Literal["IN_PROGRESS", "DONE"]] = None

    updated_at: Optional[datetime] = None
    """The timestamp when the message was last updated"""
