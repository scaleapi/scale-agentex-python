"""ACP (Agent Communication Protocol) handler for Agentex.

This is the API layer — it owns the agent lifecycle and streams tokens
and tool calls from the Pydantic AI agent to the Agentex frontend.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

import agentex.lib.adk as adk
from project.agent import create_agent
from agentex.lib.adk import (
    create_pydantic_ai_tracing_handler,
    convert_pydantic_ai_to_agentex_events,
)
from agentex.lib.types.acp import SendMessageParams
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.types.task_message_update import TaskMessageUpdate
from agentex.types.task_message_content import TaskMessageContent
from agentex.lib.core.tracing.tracing_processor_manager import add_tracing_processor_config

logger = make_logger(__name__)

add_tracing_processor_config(
    SGPTracingProcessorConfig(
        sgp_api_key=os.environ.get("SGP_API_KEY", ""),
        sgp_account_id=os.environ.get("SGP_ACCOUNT_ID", ""),
        sgp_base_url=os.environ.get("SGP_CLIENT_BASE_URL", ""),
    )
)

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
    task_id = params.task.id

    user_message = params.content.content
    logger.info(f"Processing message for task {task_id}")

    async with adk.tracing.span(
        trace_id=task_id,
        task_id=task_id,
        name="message",
        input={"message": user_message},
        data={"__span_type__": "AGENT_WORKFLOW"},
    ) as turn_span:
        tracing_handler = create_pydantic_ai_tracing_handler(
            trace_id=task_id,
            parent_span_id=turn_span.id if turn_span else None,
            task_id=task_id,
        )
        async with agent.run_stream_events(user_message) as stream:
            async for event in convert_pydantic_ai_to_agentex_events(stream, tracing_handler=tracing_handler):
                yield event
