"""ACP (Agent Communication Protocol) handler for Agentex.

This is the API layer — it owns the agent lifecycle and streams tokens
and tool calls from the Pydantic AI agent to the Agentex frontend.
"""

from __future__ import annotations

from typing import AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

from project.agent import create_agent
from agentex.lib.adk import convert_pydantic_ai_to_agentex_events
from agentex.lib.types.acp import SendMessageParams
from agentex.lib.utils.logging import make_logger
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.types.task_message_update import TaskMessageUpdate
from agentex.types.task_message_content import TaskMessageContent

logger = make_logger(__name__)

acp = FastACP.create(acp_type="sync")

_agent = None


def get_agent():
    """Get or create the Pydantic AI agent instance."""
    global _agent
    if _agent is None:
        _agent = create_agent()
    return _agent


@acp.on_message_send
async def handle_message_send(
    params: SendMessageParams,
) -> TaskMessageContent | list[TaskMessageContent] | AsyncGenerator[TaskMessageUpdate, None]:
    """Handle incoming messages from Agentex, streaming tokens and tool calls."""
    agent = get_agent()

    user_message = params.content.content
    logger.info(f"Processing message for task {params.task.id}")

    async with agent.run_stream_events(user_message) as stream:
        async for event in convert_pydantic_ai_to_agentex_events(stream):
            yield event
