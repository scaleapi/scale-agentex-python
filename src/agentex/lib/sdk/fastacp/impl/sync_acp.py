from collections.abc import AsyncGenerator
from typing import Any, override

from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer
from agentex.lib.types.acp import SendMessageParams
from agentex.lib.types.task_message_updates import (
    StreamTaskMessageDelta,
    StreamTaskMessageFull,
    TaskMessageUpdate,
    TextDelta,
)
from agentex.types.task_message_content import TaskMessageContent, TextContent
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class SyncACP(BaseACPServer):
    """
    SyncACP provides synchronous request-response style communication.
    Handlers execute and return responses immediately.

    The SyncACP automatically creates input and output messages, so handlers
    don't need to manually create TaskMessage objects via the Agentex API. All that needs
    to be done is return the output message via TaskMessageContent objects.

    Usage:
        acp = SyncACP()

        @acp.on_message_send
        async def handle_message(params: SendMessageParams) -> TaskMessageContent:
            # Process message and return response
            pass

        acp.run()
    """

    def __init__(self):
        super().__init__()
        self._setup_handlers()

    @classmethod
    @override
    def create(cls, **kwargs: Any) -> "SyncACP":
        """Create and initialize SyncACP instance

        Args:
            **kwargs: Configuration parameters (unused in sync implementation)

        Returns:
            Initialized SyncACP instance
        """
        logger.info("Creating SyncACP instance")
        instance = cls()
        logger.info("SyncACP instance created with default handlers")
        return instance

    @override
    def _setup_handlers(self):
        """Set up default handlers for sync operations"""

        @self.on_message_send
        async def handle_message_send(  # type: ignore[unused-function]
            params: SendMessageParams
        ) -> TaskMessageContent | AsyncGenerator[TaskMessageUpdate, None]:
            """Default message handler with TaskMessageUpdate streaming support

            For streaming, the SyncACP server automatically creates the input and output
            messages, so we just return TaskMessageUpdate objects with parent_task_message=None
            """
            logger.info(
                f"SyncACP received message for task {params.task.id}: {params.content}"
            )

            if params.stream:
                # Return streaming response
                async def stream_response():
                    # Example: Stream 3 chunks
                    full_message = ""
                    for i in range(3):
                        data = f"Streaming chunk {i+1}: Processing your request...\n"
                        full_message += data
                        yield StreamTaskMessageDelta(
                            type="delta",
                            index=0,
                            delta=TextDelta(
                                text_delta=f"Streaming chunk {i+1}: Processing your request...\n"
                            ),
                        )

                    # Final response
                    yield StreamTaskMessageFull(
                        type="full",
                        index=0,
                        content=TextContent(
                            author="agent",
                            content=full_message,
                            format="markdown",
                        ),
                    )

                return stream_response()
            else:
                # Return single response for non-streaming
                return TextContent(
                    author="agent",
                    content=f"Processed message for task {params.task.id}",
                    format="markdown",
                )
