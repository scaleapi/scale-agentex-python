from temporalio.common import RetryPolicy

from agentex import AsyncAgentex
from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.adapters.streams.adapter_redis import RedisStreamRepository
from agentex.lib.core.services.adk.streaming import (
    StreamingService,
    StreamingTaskMessageContext,
)
from agentex.types.task_message_content import TaskMessageContent
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import in_temporal_workflow

logger = make_logger(__name__)

DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


class StreamingModule:
    """
    Module for streaming content to clients in Agentex.

    This interface wraps around the StreamingService and provides a high-level API
    for streaming events to clients, supporting both synchronous and asynchronous
    (Temporal workflow) contexts.
    """

    def __init__(self, streaming_service: StreamingService | None = None):
        """
        Initialize the streaming interface.

        Args:
            streaming_service (Optional[StreamingService]): Optional StreamingService instance. If not provided,
                a new service will be created with default parameters.
        """
        if streaming_service is None:
            stream_repository = RedisStreamRepository()
            agentex_client = create_async_agentex_client()
            self._streaming_service = StreamingService(
                agentex_client=agentex_client,
                stream_repository=stream_repository,
            )
        else:
            self._streaming_service = streaming_service

    def streaming_task_message_context(
        self,
        task_id: str,
        initial_content: TaskMessageContent,
    ) -> StreamingTaskMessageContext:
        """
        Create a streaming context for managing TaskMessage lifecycle.

        This is a context manager that automatically creates a TaskMessage, sends START event,
        and sends DONE event when the context exits. Perfect for simple streaming scenarios.

        Args:
            task_id: The ID of the task
            initial_content: The initial content for the TaskMessage
            agentex_client: The agentex client for creating/updating messages

        Returns:
            StreamingTaskMessageContext: Context manager for streaming operations
        """
        # Note: We don't support Temporal activities for streaming context methods yet
        # since they involve complex state management across multiple activity calls
        if in_temporal_workflow():
            logger.warning(
                "Streaming context methods are not yet supported in Temporal workflows. "
                "You should wrap the entire streaming context in an activity. All nondeterministic network calls should be wrapped in an activity and generators cannot operate across activities and workflows."
            )

        return self._streaming_service.streaming_task_message_context(
            task_id=task_id,
            initial_content=initial_content,
        )
