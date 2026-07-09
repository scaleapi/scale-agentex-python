# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime
from typing_extensions import Literal

from ..._models import BaseModel
from ..message_author import MessageAuthor

__all__ = ["ScheduleResumeByNameResponse", "InitialInput", "CreatorPrincipal"]


class InitialInput(BaseModel):
    """The initial input."""

    content: str
    """The initial prompt delivered to the task."""

    author: Optional[MessageAuthor] = None
    """The author attributed to the initial input."""

    type: Optional[Literal["text"]] = None
    """Input content type."""


class CreatorPrincipal(BaseModel):
    """Credential-free creator identity stored with the schedule.

    Never carries cookies, JWTs, API keys, OAuth tokens, or request headers — it
    is creator *context* used only for AuthZ and ownership at fire time.
    """

    account_id: Optional[str] = None
    """Account/workspace id of the creator."""

    principal_type: Optional[str] = None
    """e.g. 'user' or 'service_account'."""

    service_account_id: Optional[str] = None
    """Creator service-account id, if a service principal."""

    user_id: Optional[str] = None
    """Creator user id, if a user principal."""


class ScheduleResumeByNameResponse(BaseModel):
    """Response model describing a scheduled agent run."""

    id: str
    """The unique identifier of the run schedule."""

    agent_id: str
    """The agent this schedule belongs to."""

    initial_input: InitialInput
    """The initial input."""

    initial_input_method: str
    """Delivery method, inferred from the agent's ACP type."""

    name: str
    """Human-readable schedule name."""

    created_at: Optional[datetime] = None
    """When the schedule was created."""

    creator_principal: Optional[CreatorPrincipal] = None
    """Credential-free creator identity stored with the schedule.

    Never carries cookies, JWTs, API keys, OAuth tokens, or request headers — it is
    creator _context_ used only for AuthZ and ownership at fire time.
    """

    cron_expression: Optional[str] = None
    """Cron cadence, if cron-based."""

    description: Optional[str] = None
    """Optional description."""

    end_at: Optional[datetime] = None
    """Schedule deactivation time."""

    interval_seconds: Optional[int] = None
    """Interval cadence in seconds, if interval-based."""

    last_action_time: Optional[datetime] = None
    """When the schedule last fired."""

    next_action_times: Optional[List[datetime]] = None
    """Upcoming scheduled fire times."""

    num_actions_taken: Optional[int] = None
    """Number of times the schedule has fired."""

    paused: Optional[bool] = None
    """Whether the schedule is paused."""

    start_at: Optional[datetime] = None
    """Schedule activation time."""

    state: Optional[Literal["ACTIVE", "PAUSED"]] = None
    """Live schedule state from Temporal."""

    task_metadata: Optional[Dict[str, object]] = None
    """Task metadata at fire time."""

    task_params: Optional[Dict[str, object]] = None
    """Task params at fire time."""

    timezone: Optional[str] = None
    """Timezone the cron expression is evaluated in."""

    updated_at: Optional[datetime] = None
    """When the schedule was updated."""
