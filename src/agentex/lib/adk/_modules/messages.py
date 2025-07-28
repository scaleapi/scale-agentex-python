from datetime import timedelta

from temporalio.common import RetryPolicy

from agentex import AsyncAgentex
from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.adapters.streams.adapter_redis import RedisStreamRepository
from agentex.lib.core.services.adk.messages import MessagesService
from agentex.lib.core.services.adk.streaming import StreamingService
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.temporal.activities.adk.messages_activities import (
    CreateMessageParams,
    CreateMessagesBatchParams,
    ListMessagesParams,
    MessagesActivityName,
    UpdateMessageParams,
    UpdateMessagesBatchParams,
)
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.task_message import TaskMessage, TaskMessageContent
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import in_temporal_workflow

logger = make_logger(__name__)

# Default retry policy for all message operations
DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


class MessagesModule:
    """
    Module for managing task messages in Agentex.
    Provides high-level async methods for creating, retrieving, updating, and deleting messages.
    """

    def __init__(
        self,
        messages_service: MessagesService | None = None,
    ):
        if messages_service is None:
            agentex_client = create_async_agentex_client()
            stream_repository = RedisStreamRepository()
            streaming_service = StreamingService(
                agentex_client=agentex_client,
                stream_repository=stream_repository,
            )
            tracer = AsyncTracer(agentex_client)
            self._messages_service = MessagesService(
                agentex_client=agentex_client,
                streaming_service=streaming_service,
                tracer=tracer,
            )
        else:
            self._messages_service = messages_service

    async def create(
        self,
        task_id: str,
        content: TaskMessageContent,
        emit_updates: bool = True,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> TaskMessage:
        """
        Create a new message for a task.

        Args:
            task_id (str): The ID of the task.
            message (TaskMessage): The message to create.
            trace_id (Optional[str]): The trace ID for tracing.
            parent_span_id (Optional[str]): The parent span ID for tracing.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            TaskMessageEntity: The created message.
        """
        params = CreateMessageParams(
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            task_id=task_id,
            content=content,
            emit_updates=emit_updates,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=MessagesActivityName.CREATE_MESSAGE,
                request=params,
                response_type=TaskMessage,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._messages_service.create_message(
                task_id=task_id,
                content=content,
                emit_updates=emit_updates,
            )

    async def update(
        self,
        task_id: str,
        message_id: str,
        content: TaskMessageContent,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> TaskMessage:
        """
        Update a message for a task.

        Args:
            task_id (str): The ID of the task.
            message_id (str): The ID of the message.
            message (TaskMessage): The message to update.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            TaskMessageEntity: The updated message.
        """
        params = UpdateMessageParams(
            task_id=task_id,
            message_id=message_id,
            content=content,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=MessagesActivityName.UPDATE_MESSAGE,
                request=params,
                response_type=TaskMessage,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._messages_service.update_message(
                task_id=task_id,
                message_id=message_id,
                content=content,
            )

    async def create_batch(
        self,
        task_id: str,
        contents: list[TaskMessageContent],
        emit_updates: bool = True,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> list[TaskMessage]:
        """
        Create a batch of messages for a task.

        Args:
            task_id (str): The ID of the task.
            messages (List[TaskMessage]): The messages to create.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            List[TaskMessageEntity]: The created messages.
        """
        params = CreateMessagesBatchParams(
            task_id=task_id,
            contents=contents,
            emit_updates=emit_updates,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=MessagesActivityName.CREATE_MESSAGES_BATCH,
                request=params,
                response_type=list[TaskMessage],
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._messages_service.create_messages_batch(
                task_id=task_id,
                contents=contents,
                emit_updates=emit_updates,
            )

    async def update_batch(
        self,
        task_id: str,
        updates: dict[str, TaskMessageContent],
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> list[TaskMessage]:
        """
        Update a batch of messages for a task.

        Args:
            task_id (str): The ID of the task.
            updates (Dict[str, TaskMessage]): The updates to apply to the messages.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            List[TaskMessageEntity]: The updated messages.
        """
        params = UpdateMessagesBatchParams(
            task_id=task_id,
            updates=updates,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=MessagesActivityName.UPDATE_MESSAGES_BATCH,
                request=params,
                response_type=list[TaskMessage],
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._messages_service.update_messages_batch(
                task_id=task_id,
                updates=updates,
            )

    async def list(
        self,
        task_id: str,
        limit: int | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=5),
        heartbeat_timeout: timedelta = timedelta(seconds=5),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> list[TaskMessage]:
        """
        List messages for a task.

        Args:
            task_id (str): The ID of the task.
            limit (Optional[int]): The maximum number of messages to return.
            start_to_close_timeout (timedelta): The start to close timeout.
            heartbeat_timeout (timedelta): The heartbeat timeout.
            retry_policy (RetryPolicy): The retry policy.

        Returns:
            List[TaskMessageEntity]: The list of messages.
        """
        params = ListMessagesParams(
            task_id=task_id,
            limit=limit,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=MessagesActivityName.LIST_MESSAGES,
                request=params,
                response_type=list[TaskMessage],
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
                heartbeat_timeout=heartbeat_timeout,
            )
        else:
            return await self._messages_service.list_messages(
                task_id=task_id,
                limit=limit,
            )
