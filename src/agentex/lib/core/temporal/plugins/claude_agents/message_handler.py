"""Message handling and streaming for Claude Agents SDK.

Simplified message handler that focuses on:
- Streaming text content to UI
- Extracting session_id for conversation continuity
- Extracting usage and cost information

Tool requests/responses are handled by Claude SDK hooks (see hooks/hooks.py).
"""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import (
    TextBlock,
    ResultMessage,
    SystemMessage,
    AssistantMessage,
)

from agentex.lib import adk
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import StreamTaskMessageDelta

logger = make_logger(__name__)


class ClaudeMessageHandler:
    """Handles Claude SDK messages and streams them to AgentEx UI.

    Simplified handler focused on:
    - Streaming text blocks to UI
    - Extracting session_id from SystemMessage/ResultMessage
    - Extracting usage and cost from ResultMessage
    - Serializing responses for Temporal

    Note: Tool lifecycle events (requests/responses) are handled by
    TemporalStreamingHooks, not this class.
    """

    def __init__(
        self,
        task_id: str | None,
        trace_id: str | None,
        parent_span_id: str | None,
    ):
        self.task_id = task_id
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id

        # Message tracking
        self.messages: list[Any] = []
        self.serialized_messages: list[dict] = []

        # Streaming context for text
        self.streaming_ctx = None

        # Result data
        self.session_id: str | None = None
        self.usage_info: dict | None = None
        self.cost_info: float | None = None

    async def initialize(self):
        """Initialize streaming context if task_id is available."""
        if self.task_id:
            logger.debug(f"Creating streaming context for task: {self.task_id}")
            self.streaming_ctx = await adk.streaming.streaming_task_message_context(
                task_id=self.task_id,
                initial_content=TextContent(
                    author="agent",
                    content="",
                    format="markdown"
                )
            ).__aenter__()

    async def handle_message(self, message: Any):
        """Process a single message from Claude SDK."""
        self.messages.append(message)
        msg_num = len(self.messages)

        # Debug logging (verbose - only for troubleshooting)
        logger.debug(f"📨 [{msg_num}] Message type: {type(message).__name__}")
        if isinstance(message, AssistantMessage):
            block_types = [type(b).__name__ for b in message.content]
            logger.debug(f"   [{msg_num}] Content blocks: {block_types}")

        # Route to specific handlers
        # Note: Tool requests/responses are handled by hooks, not here!
        if isinstance(message, AssistantMessage):
            await self._handle_assistant_message(message, msg_num)
        elif isinstance(message, SystemMessage):
            await self._handle_system_message(message)
        elif isinstance(message, ResultMessage):
            await self._handle_result_message(message)

    async def _handle_assistant_message(self, message: AssistantMessage, _msg_num: int):
        """Handle AssistantMessage - contains text blocks.

        Note: Tool calls (ToolUseBlock/ToolResultBlock) are handled by hooks, not here.
        We only process TextBlock for streaming text to UI.
        """
        # Stream text blocks to UI
        for block in message.content:
            if isinstance(block, TextBlock):
                await self._handle_text_block(block)

        # Collect text for final response
        text_content = []
        for block in message.content:
            if isinstance(block, TextBlock):
                text_content.append(block.text)

        if text_content:
            self.serialized_messages.append({
                "role": "assistant",
                "content": "\n".join(text_content)
            })

    async def _handle_text_block(self, block: TextBlock):
        """Handle text content block."""
        if not block.text or not self.streaming_ctx:
            return

        logger.debug(f"💬 Text block: {block.text[:50]}...")

        delta = TextDelta(type="text", text_delta=block.text)

        try:
            await self.streaming_ctx.stream_update(
                StreamTaskMessageDelta(
                    parent_task_message=self.streaming_ctx.task_message,
                    delta=delta,
                    type="delta"
                )
            )
        except Exception as e:
            logger.warning(f"Failed to stream text delta: {e}")

    async def _handle_system_message(self, message: SystemMessage):
        """Handle system message - extract session_id."""
        if message.subtype == "init":
            self.session_id = message.data.get("session_id")
            logger.debug(f"Session initialized: {self.session_id[:16] if self.session_id else 'unknown'}...")
        else:
            logger.debug(f"SystemMessage: {message.subtype}")

    async def _handle_result_message(self, message: ResultMessage):
        """Handle result message - extract usage and cost."""
        self.usage_info = message.usage
        self.cost_info = message.total_cost_usd

        # Update session_id if available
        if message.session_id:
            self.session_id = message.session_id

        logger.info(f"💰 Cost: ${self.cost_info:.4f}, Duration: {message.duration_ms}ms, Turns: {message.num_turns}")

    async def cleanup(self):
        """Clean up open streaming contexts."""
        if self.streaming_ctx:
            try:
                await self.streaming_ctx.close()
                logger.debug(f"Closed streaming context")
            except Exception as e:
                logger.warning(f"Failed to close streaming context: {e}")

    def get_results(self) -> dict[str, Any]:
        """Get final results for Temporal."""
        return {
            "messages": self.serialized_messages,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "usage": self.usage_info,
            "cost_usd": self.cost_info,
        }
