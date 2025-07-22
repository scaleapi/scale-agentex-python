from collections.abc import Callable
from datetime import timedelta
from typing import Any

from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import RetryPolicy as TemporalRetryPolicy
from temporalio.common import WorkflowIDReusePolicy
from temporalio.service import RPCError, RPCStatusCode

from agentex.lib.core.clients.temporal.types import (
    DuplicateWorkflowPolicy,
    RetryPolicy,
    TaskStatus,
    WorkflowState,
)
from agentex.lib.core.clients.temporal.utils import get_temporal_client
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel

logger = make_logger(__name__)

DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


TEMPORAL_STATUS_TO_UPLOAD_STATUS_AND_REASON = {
    # TODO: Support canceled status
    WorkflowExecutionStatus.CANCELED: WorkflowState(
        status=TaskStatus.CANCELED,
        reason="Task canceled by the user.",
        is_terminal=True,
    ),
    WorkflowExecutionStatus.COMPLETED: WorkflowState(
        status=TaskStatus.COMPLETED,
        reason="Task completed successfully.",
        is_terminal=True,
    ),
    WorkflowExecutionStatus.FAILED: WorkflowState(
        status=TaskStatus.FAILED,
        reason="Task encountered terminal failure. "
        "Please contact support if retrying does not resolve the issue.",
        is_terminal=True,
    ),
    WorkflowExecutionStatus.RUNNING: WorkflowState(
        status=TaskStatus.RUNNING,
        reason="Task is running.",
        is_terminal=False,
    ),
    WorkflowExecutionStatus.TERMINATED: WorkflowState(
        status=TaskStatus.CANCELED,
        reason="Task canceled by the user.",
        is_terminal=True,
    ),
    WorkflowExecutionStatus.TIMED_OUT: WorkflowState(
        status=TaskStatus.FAILED,
        reason="Task timed out. Please contact support if retrying does not resolve the issue",
        is_terminal=True,
    ),
    WorkflowExecutionStatus.CONTINUED_AS_NEW: WorkflowState(
        status=TaskStatus.RUNNING,
        reason="Task is running.",
        is_terminal=False,
    ),
}

DUPLICATE_POLICY_TO_ID_REUSE_POLICY = {
    DuplicateWorkflowPolicy.ALLOW_DUPLICATE: WorkflowIDReusePolicy.ALLOW_DUPLICATE,
    DuplicateWorkflowPolicy.ALLOW_DUPLICATE_FAILED_ONLY: WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
    DuplicateWorkflowPolicy.REJECT_DUPLICATE: WorkflowIDReusePolicy.REJECT_DUPLICATE,
    DuplicateWorkflowPolicy.TERMINATE_IF_RUNNING: WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
}


class TemporalClient:
    def __init__(self, temporal_client: Client | None = None):
        self._client: Client = temporal_client

    @classmethod
    async def create(cls, temporal_address: str):
        if temporal_address in [
            "false",
            "False",
            "null",
            "None",
            "",
            "undefined",
            False,
            None,
        ]:
            _client = None
        else:
            _client = await get_temporal_client(temporal_address)
        return cls(_client)

    async def setup(self, temporal_address: str):
        self._client = await self._get_temporal_client(
            temporal_address=temporal_address
        )

    async def _get_temporal_client(self, temporal_address: str) -> Client:
        if temporal_address in [
            "false",
            "False",
            "null",
            "None",
            "",
            "undefined",
            False,
            None,
        ]:
            return None
        else:
            return await get_temporal_client(temporal_address)

    async def start_workflow(
        self,
        *args: Any,
        duplicate_policy: DuplicateWorkflowPolicy = DuplicateWorkflowPolicy.ALLOW_DUPLICATE,
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
        task_timeout: timedelta = timedelta(seconds=10),
        execution_timeout: timedelta = timedelta(seconds=86400),
        **kwargs: Any,
    ) -> str:
        temporal_retry_policy = TemporalRetryPolicy(
            **retry_policy.model_dump(exclude_unset=True)
        )
        workflow_handle = await self._client.start_workflow(
            *args,
            retry_policy=temporal_retry_policy,
            task_timeout=task_timeout,
            execution_timeout=execution_timeout,
            id_reuse_policy=DUPLICATE_POLICY_TO_ID_REUSE_POLICY[duplicate_policy],
            **kwargs,
        )
        return workflow_handle.id

    async def send_signal(
        self,
        workflow_id: str,
        signal: str | Callable[[dict[str, Any] | list[Any] | str | int | float | bool | BaseModel], Any],
        payload: dict[str, Any] | list[Any] | str | int | float | bool | BaseModel,
    ) -> None:
        handle = self._client.get_workflow_handle(workflow_id=workflow_id)
        await handle.signal(signal, payload)

    async def query_workflow(
        self,
        workflow_id: str,
        query: str | Callable[[dict[str, Any] | list[Any] | str | int | float | bool | BaseModel], Any],
    ) -> Any:
        """
        Submit a query to a workflow by name and return the results.

        Args:
            workflow_id: The ID of the workflow to query
            query: The name of the query or a callable query function

        Returns:
            The result of the query
        """
        handle = self._client.get_workflow_handle(workflow_id=workflow_id)
        return await handle.query(query)

    async def get_workflow_status(self, workflow_id: str) -> WorkflowState:
        try:
            handle = self._client.get_workflow_handle(workflow_id=workflow_id)
            description = await handle.describe()
            return TEMPORAL_STATUS_TO_UPLOAD_STATUS_AND_REASON[description.status]
        except RPCError as e:
            if e.status == RPCStatusCode.NOT_FOUND:
                return WorkflowState(
                    status="NOT_FOUND",
                    reason="Workflow not found",
                    is_terminal=True,
                )
            raise

    async def terminate_workflow(self, workflow_id: str) -> None:
        return await self._client.get_workflow_handle(workflow_id).terminate()

    async def cancel_workflow(self, workflow_id: str) -> None:
        return await self._client.get_workflow_handle(workflow_id).cancel()
