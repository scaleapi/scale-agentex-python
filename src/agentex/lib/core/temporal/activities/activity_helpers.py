from __future__ import annotations

from typing import Any, TypeVar
from datetime import timedelta

from pydantic import TypeAdapter
from temporalio import workflow
from temporalio.common import RetryPolicy

from agentex.lib.utils.model_utils import BaseModel

T = TypeVar("T", bound="BaseModel")


class ActivityHelpers:
    @staticmethod
    async def execute_activity(
        activity_name: str,
        request: BaseModel | str | int | float | bool | dict[str, Any] | list[Any],
        response_type: Any,
        start_to_close_timeout: timedelta | None = None,
        heartbeat_timeout: timedelta | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> Any:

        response = await workflow.execute_activity(
            activity=activity_name,
            arg=request,
            start_to_close_timeout=start_to_close_timeout,
            retry_policy=retry_policy,
            heartbeat_timeout=heartbeat_timeout,
        )

        adapter = TypeAdapter(response_type)
        return adapter.validate_python(response)
