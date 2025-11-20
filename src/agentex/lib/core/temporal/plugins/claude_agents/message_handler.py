"""Message handling and streaming for Claude Agents SDK."""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    UserMessage,
    TextBlock,
    SystemMessage,
    ResultMessage,
    ToolUseBlock,
    ToolResultBlock,
)

from agentex.lib.utils.logging import make_logger
from agentex.lib import adk
from agentex.types.text_content import TextContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import StreamTaskMessageDelta, StreamTaskMessageFull

logger = make_logger(__name__)


class ClaudeMessageHandler:
    """Handles Claude SDK messages and streams them to AgentEx UI.

    Responsibilities:
    - Parse Claude SDK message types (AssistantMessage, UserMessage, etc.)
    - Stream tool requests/responses to UI
    - Track session_id for conversation continuity
    - Create nested spans for subagent execution
    - Extract usage and cost information
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

        # Streaming contexts
        self.streaming_ctx = None
        self.tool_call_map: dict[str, str] = {}  # tool_call_id → tool_name
        self.last_tool_call_id: str | None = None

        # Subagent tracking
        self.current_subagent_span = None
        self.current_subagent_ctx = None

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
        if isinstance(message, UserMessage):
            await self._handle_user_message(message, msg_num)
        elif isinstance(message, AssistantMessage):
            await self._handle_assistant_message(message, msg_num)
        elif isinstance(message, SystemMessage):
            await self._handle_system_message(message)
        elif isinstance(message, ResultMessage):
            await self._handle_result_message(message)

    async def _handle_user_message(self, message: UserMessage, msg_num: int):
        """Handle UserMessage - tool results when permission_mode=acceptEdits."""
        if not self.last_tool_call_id or not self.task_id:
            return

        tool_name = self.tool_call_map.get(self.last_tool_call_id, "unknown")
        logger.info(f"✅ Tool result: {tool_name}")

        # If this was a subagent (Task tool), close the subagent span
        if tool_name == "Task" and self.current_subagent_span and self.current_subagent_ctx:
            user_content = message.content
            if isinstance(user_content, list):
                user_content = str(user_content)

            self.current_subagent_span.output = {"result": user_content}
            await self.current_subagent_ctx.__aexit__(None, None, None)
            logger.info(f"🤖 Subagent completed: {tool_name}")
            self.current_subagent_span = None
            self.current_subagent_ctx = None

        # Extract and stream tool result
        user_content = message.content
        if isinstance(user_content, list):
            user_content = str(user_content)

        try:
            async with adk.streaming.streaming_task_message_context(
                task_id=self.task_id,
                initial_content=ToolResponseContent(
                    author="agent",
                    name=tool_name,
                    content=user_content,
                    tool_call_id=self.last_tool_call_id,
                )
            ) as tool_ctx:
                await tool_ctx.stream_update(
                    StreamTaskMessageFull(
                        parent_task_message=tool_ctx.task_message,
                        content=ToolResponseContent(
                            author="agent",
                            name=tool_name,
                            content=user_content,
                            tool_call_id=self.last_tool_call_id,
                        ),
                        type="full"
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to stream tool response: {e}")

        # Clear the last tool call
        self.last_tool_call_id = None

    async def _handle_assistant_message(self, message: AssistantMessage, msg_num: int):
        """Handle AssistantMessage - contains text blocks and tool calls."""
        for block in message.content:
            if isinstance(block, ToolUseBlock):
                await self._handle_tool_use(block, msg_num)
            elif isinstance(block, ToolResultBlock):
                await self._handle_tool_result(block)
            elif isinstance(block, TextBlock):
                await self._handle_text_block(block, msg_num)

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

    async def _handle_tool_use(self, block: ToolUseBlock, msg_num: int):
        """Handle tool request block."""
        if not self.task_id:
            return

        logger.info(f"🔧 Tool request: {block.name}")

        # Track tool_call_id → tool_name mapping
        self.tool_call_map[block.id] = block.name
        self.last_tool_call_id = block.id

        # Special handling for Task tool (subagents) - create nested span
        if block.name == "Task" and self.trace_id and self.parent_span_id:
            subagent_type = block.input.get("subagent_type", "unknown")
            logger.info(f"🤖 Subagent started: {subagent_type}")

            # Create nested trace span
            self.current_subagent_ctx = adk.tracing.span(
                trace_id=self.trace_id,
                parent_id=self.parent_span_id,
                name=f"Subagent: {subagent_type}",
                input=block.input,
            )
            self.current_subagent_span = await self.current_subagent_ctx.__aenter__()

        # Stream tool request
        try:
            async with adk.streaming.streaming_task_message_context(
                task_id=self.task_id,
                initial_content=ToolRequestContent(
                    author="agent",
                    name=block.name,
                    arguments=block.input,
                    tool_call_id=block.id,
                )
            ) as tool_ctx:
                await tool_ctx.stream_update(
                    StreamTaskMessageFull(
                        parent_task_message=tool_ctx.task_message,
                        content=ToolRequestContent(
                            author="agent",
                            name=block.name,
                            arguments=block.input,
                            tool_call_id=block.id,
                        ),
                        type="full"
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to stream tool request: {e}")

    async def _handle_tool_result(self, block: ToolResultBlock):
        """Handle tool result block (when not using acceptEdits)."""
        if not self.task_id:
            return

        tool_name = self.tool_call_map.get(block.tool_use_id, "unknown")
        logger.info(f"✅ Tool result: {tool_name}")

        tool_content = block.content if block.content is not None else ""

        try:
            async with adk.streaming.streaming_task_message_context(
                task_id=self.task_id,
                initial_content=ToolResponseContent(
                    author="agent",
                    name=tool_name,
                    content=tool_content,
                    tool_call_id=block.tool_use_id,
                )
            ) as tool_ctx:
                await tool_ctx.stream_update(
                    StreamTaskMessageFull(
                        parent_task_message=tool_ctx.task_message,
                        content=ToolResponseContent(
                            author="agent",
                            name=tool_name,
                            content=tool_content,
                            tool_call_id=block.tool_use_id,
                        ),
                        type="full"
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to stream tool response: {e}")

    async def _handle_text_block(self, block: TextBlock, msg_num: int):
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
