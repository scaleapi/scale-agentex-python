from datetime import timedelta
from typing import Any

from temporalio.common import RetryPolicy

from agentex import AsyncAgentex
from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.services.adk.acp.acp import ACPService
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.temporal.activities.adk.acp.acp_activities import (
    ACPActivityName,
    EventSendParams,
    MessageSendParams,
    TaskCancelParams,
    TaskCreateParams,
)
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.task_message import TaskMessage
from agentex.types.task import Task
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import in_temporal_workflow
from agentex.types.task_message_content import TaskMessageContent

logger = make_logger(__name__)

DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


class ACPModule:
    """
    Module for managing Agent to Client Protocol (ACP) agent operations in Agentex.

    This interface provides high-level methods for interacting with the agent through the ACP.
    """

    def __init__(self, acp_service: ACPService | None = None):
        """
        Initialize the ACP module.

        Args:
            acp_activities (Optional[ACPActivities]): Optional pre-configured ACP activities. If None, will be auto-initialized.
        """
        if acp_service is None:
            agentex_client = create_async_agentex_client()
            tracer = AsyncTracer(agentex_client)
            self._acp_service = ACPService(agentex_client=agentex_client, tracer=tracer)
        else:
            self._acp_service = acp_service

    async def create_task(
        self,
        name: str | None = None,
        agent_id: str | None = None,
        agent_name: str | None = None,
        params: dict[str, Any] | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ):
        """
        Create a new task.

        Args:
            name: The name of the task.
            agent_id: The ID of the agent to create the task for.
            agent_name: The name of the agent to create the task for.
            params: The parameters for the task.
            start_to_close_timeout: The start to close timeout for the task.
            heartbeat_timeout: The heartbeat timeout for the task.
            retry_policy: The retry policy for the task.

        Returns:
            The task entry.
        """
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=ACPActivityName.TASK_CREATE,
                request=TaskCreateParams(
                    name=name,
                    agent_id=agent_id,
                    agent_name=agent_name,
                    params=params,
                    trace_id=trace_id,
                    parent_span_id=parent_span_id,
                ),
                response_type=Task,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,  
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._acp_service.task_create(
                name=name,
                agent_id=agent_id,
                agent_name=agent_name,
                params=params,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def send_event(
        self,
        task_id: str,
        content: TaskMessageContent,
        agent_id: str | None = None,
        agent_name: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ):
        """
        Send an event to a task.

        Args:
            task_id: The ID of the task to send the event to.
            data: The data to send to the event.
            agent_id: The ID of the agent to send the event to.
            agent_name: The name of the agent to send the event to.

        Returns:
            The event entry.
        """
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=ACPActivityName.EVENT_SEND,
                request=EventSendParams(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    task_id=task_id,
                    content=content,
                    trace_id=trace_id,
                    parent_span_id=parent_span_id,
                ),
                response_type=None,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._acp_service.event_send(
                agent_id=agent_id,
                agent_name=agent_name,
                task_id=task_id,
                content=content,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def send_message(
        self,
        task_id: str,
        content: TaskMessageContent,
        agent_id: str | None = None,
        agent_name: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ):
        """
        Send a message to a task.

        Args:
            task_id: The ID of the task to send the message to.
            content: The task message content to send to the task.
            agent_id: The ID of the agent to send the message to.
            agent_name: The name of the agent to send the message to.

        Returns:
            The message entry.
        """
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=ACPActivityName.MESSAGE_SEND,
                request=MessageSendParams(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    task_id=task_id,
                    content=content,
                    trace_id=trace_id,
                    parent_span_id=parent_span_id,
                ),
                response_type=TaskMessage,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._acp_service.message_send(
                agent_id=agent_id,
                agent_name=agent_name,
                task_id=task_id,
                content=content,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

    async def cancel_task(
        self,
        task_id: str | None = None,
        task_name: str | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ):
        """
        Cancel a task.

        Args:
            task_id: The ID of the task to cancel.
            task_name: The name of the task to cancel.
            trace_id: The trace ID for the task.
            parent_span_id: The parent span ID for the task.
            start_to_close_timeout: The start to close timeout for the task.
            heartbeat_timeout: The heartbeat timeout for the task.
            retry_policy: The retry policy for the task.

        Returns:
            The task entry.
        """
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=ACPActivityName.TASK_CANCEL,
                request=TaskCancelParams(
                    task_id=task_id,
                    task_name=task_name,
                    trace_id=trace_id,
                    parent_span_id=parent_span_id,
                ),
                response_type=None,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._acp_service.task_cancel(
                task_id=task_id,
                task_name=task_name,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )
