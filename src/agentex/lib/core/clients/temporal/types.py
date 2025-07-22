from datetime import timedelta
from enum import Enum

from pydantic import Field

from agentex.lib.utils.model_utils import BaseModel


class WorkflowState(BaseModel):
    status: str
    is_terminal: bool
    reason: str | None = None


class RetryPolicy(BaseModel):
    initial_interval: timedelta = Field(
        timedelta(seconds=1),
        description="Backoff interval for the first retry. Default 1s.",
    )
    backoff_coefficient: float = Field(
        2.0,
        description="Coefficient to multiply previous backoff interval by to get new interval. Default 2.0.",
    )
    maximum_interval: timedelta | None = Field(
        None,
        description="Maximum backoff interval between retries. Default 100x :py:attr:`initial_interval`.",
    )
    maximum_attempts: int = Field(
        0,
        description="Maximum number of attempts. If 0, the default, there is no maximum.",
    )


class DuplicateWorkflowPolicy(str, Enum):
    ALLOW_DUPLICATE = "ALLOW_DUPLICATE"
    ALLOW_DUPLICATE_FAILED_ONLY = "ALLOW_DUPLICATE_FAILED_ONLY"
    REJECT_DUPLICATE = "REJECT_DUPLICATE"
    TERMINATE_IF_RUNNING = "TERMINATE_IF_RUNNING"


class TaskStatus(str, Enum):
    CANCELED = "CANCELED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RUNNING = "RUNNING"
    TERMINATED = "TERMINATED"
    TIMED_OUT = "TIMED_OUT"
