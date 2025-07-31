from typing import Any

from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from typing_extensions import override
from agentex import AsyncAgentex
from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer
from agentex.lib.types.acp import (
    CancelTaskParams,
    CreateTaskParams,
    SendEventParams,
)
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class AgenticBaseACP(BaseACPServer):
    """
    AgenticBaseACP implementation - a synchronous ACP that provides basic functionality
    without any special async orchestration like Temporal.

    This implementation provides simple synchronous processing of tasks
    and is suitable for basic agent implementations.
    """

    def __init__(self):
        super().__init__()
        self._setup_handlers()
        self._agentex_client = create_async_agentex_client()

    @classmethod
    @override
    def create(cls, **kwargs: Any) -> "AgenticBaseACP":
        """Create and initialize SyncACP instance

        Args:
            **kwargs: Configuration parameters (unused in sync implementation)

        Returns:
            Initialized SyncACP instance
        """
        logger.info("Initializing AgenticBaseACP instance")
        instance = cls()
        logger.info("AgenticBaseACP instance initialized with default handlers")
        return instance

    @override
    def _setup_handlers(self):
        """Set up default handlers for sync operations"""

        @self.on_task_create
        async def handle_create_task(params: CreateTaskParams) -> None:  # type: ignore[unused-function]
            """Default create task handler - logs the task"""
            logger.info(f"AgenticBaseACP creating task {params.task.id}")

        @self.on_task_event_send
        async def handle_event_send(params: SendEventParams) -> None:  # type: ignore[unused-function]
            """Default event handler - logs the event"""
            logger.info(
                f"AgenticBaseACP received event for task {params.task.id}: {params.event.id},"
                f"content: {params.event.content}"
            )
            # TODO: Implement event handling logic here

            # Implement cursor commit logic here
            await self._agentex_client.tracker.update(
                tracker_id=params.task.id,
                last_processed_event_id=params.event.id,
            )

        @self.on_task_cancel
        async def handle_cancel(params: CancelTaskParams) -> None:  # type: ignore[unused-function]
            """Default cancel handler - logs the cancellation"""
            logger.info(f"AgenticBaseACP canceling task {params.task.id}")
