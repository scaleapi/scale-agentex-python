"""Claude Agents SDK integration with Temporal - MVP v0

This module provides minimal integration between Claude Agents SDK and AgentEx's
Temporal-based architecture.

MVP v0 Features:
- Basic activity wrapper for Claude SDK calls
- Text streaming to Redis/UI
- Workspace isolation via cwd parameter
- Reuses OpenAI's ContextInterceptor for context threading

What's missing (see examples/tutorials/10_async/10_temporal/090_claude_agents_sdk_mvp/NEXT_STEPS.md):
- Automatic plugin (manual activity wrapping for now)
- Tool call streaming
- Tracing wrapper
- Subagents
- Tests
"""

from __future__ import annotations

from typing import Any
from datetime import timedelta

from temporalio import activity
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock

# Reuse OpenAI's context threading - this is the key to streaming!
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import (
    ContextInterceptor,
    streaming_task_id,
    streaming_trace_id,
    streaming_parent_span_id,
)

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


@activity.defn(name="run_claude_agent_activity")
async def run_claude_agent_activity(
    prompt: str,
    workspace_path: str,
    allowed_tools: list[str],
    permission_mode: str = "acceptEdits",
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Execute Claude SDK - wrapped in Temporal activity

    This activity:
    1. Gets task_id from ContextVar (set by ContextInterceptor)
    2. Configures Claude with workspace isolation
    3. Runs Claude SDK and collects responses
    4. Returns messages for Temporal determinism

    Args:
        prompt: User message to send to Claude
        workspace_path: Directory for file operations (cwd)
        allowed_tools: List of tools Claude can use
        permission_mode: Permission mode (default: acceptEdits)
        system_prompt: Optional system prompt override

    Returns:
        dict with "messages" key containing Claude's responses
    """

    # Get streaming context from ContextVars (set by interceptor)
    task_id = streaming_task_id.get()
    trace_id = streaming_trace_id.get()
    parent_span_id = streaming_parent_span_id.get()

    logger.info(
        f"[run_claude_agent_activity] Starting - "
        f"task_id={task_id}, workspace={workspace_path}, tools={allowed_tools}"
    )

    # Configure Claude with workspace isolation
    options = ClaudeAgentOptions(
        cwd=workspace_path,
        allowed_tools=allowed_tools,
        permission_mode=permission_mode,  # type: ignore
        system_prompt=system_prompt,
    )

    # Run Claude and collect results
    messages = []
    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                messages.append(message)
                logger.debug(f"[run_claude_agent_activity] Received message: {type(message).__name__}")

                # Basic text extraction for MVP
                # TODO: Add proper streaming in Commit 4
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            logger.debug(f"[run_claude_agent_activity] Text block: {block.text[:100]}...")

    except Exception as e:
        logger.error(f"[run_claude_agent_activity] Error: {e}", exc_info=True)
        raise

    logger.info(f"[run_claude_agent_activity] Completed - collected {len(messages)} messages")

    # Serialize messages for Temporal
    serialized_messages = []
    for msg in messages:
        if isinstance(msg, AssistantMessage):
            text_content = []
            for block in msg.content:
                if isinstance(block, TextBlock):
                    text_content.append(block.text)
            serialized_messages.append({
                "role": "assistant",
                "content": "\n".join(text_content)
            })
        else:
            serialized_messages.append({"type": type(msg).__name__, "content": str(msg)})

    return {
        "messages": serialized_messages,
        "task_id": task_id,
    }


__all__ = [
    "run_claude_agent_activity",
    "ContextInterceptor",  # Reuse from OpenAI - no changes needed!
    "streaming_task_id",
    "streaming_trace_id",
    "streaming_parent_span_id",
]
