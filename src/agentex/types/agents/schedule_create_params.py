# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["ScheduleCreateParams"]


class ScheduleCreateParams(TypedDict, total=False):
    name: Required[str]
    """Human-readable name for the schedule (e.g., 'weekly-profiling').

    Will be combined with agent_id to form the full schedule_id.
    """

    task_queue: Required[str]
    """Temporal task queue where the agent's worker is listening"""

    workflow_name: Required[str]
    """Name of the Temporal workflow to execute (e.g., 'sae-orchestrator')"""

    cron_expression: Optional[str]
    """Cron expression for scheduling (e.g., '0 0 \\** \\** 0' for weekly on Sunday)"""

    end_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """When the schedule should stop being active"""

    execution_timeout_seconds: Optional[int]
    """Maximum time in seconds for each workflow execution"""

    interval_seconds: Optional[int]
    """Alternative to cron - run every N seconds"""

    paused: bool
    """Whether to create the schedule in a paused state"""

    start_at: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """When the schedule should start being active"""

    workflow_params: Optional[Dict[str, object]]
    """Parameters to pass to the workflow"""
