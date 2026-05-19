"""ACP handler for async Pydantic AI agent.

Uses the async ACP model with Redis streaming instead of HTTP yields.
Text and reasoning tokens stream as Redis deltas; tool requests and
responses are persisted as discrete full messages.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

import agentex.lib.adk as adk
from project.agent import create_agent
from agentex.lib.adk import (
    stream_pydantic_ai_events,
    create_pydantic_ai_tracing_handler,
)
from agentex.lib.types.acp import SendEventParams, CancelTaskParams, CreateTaskParams
from agentex.lib.types.fastacp import AsyncACPConfig
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.core.tracing.tracing_processor_manager import add_tracing_processor_config

logger = make_logger(__name__)

add_tracing_processor_config(
    SGPTracingProcessorConfig(
        sgp_api_key=os.environ.get("SGP_API_KEY", ""),
        sgp_account_id=os.environ.get("SGP_ACCOUNT_ID", ""),
        sgp_base_url=os.environ.get("SGP_CLIENT_BASE_URL", ""),
    )
)

acp = FastACP.create(
    acp_type="async",
    config=AsyncACPConfig(type="base"),
)

_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent()
    return _agent


@acp.on_task_event_send
async def handle_task_event_send(params: SendEventParams):
    """Handle incoming events, streaming tokens and tool calls via Redis."""
    agent = get_agent()
    task_id = params.task.id
    user_message = params.event.content.content

    logger.info(f"Processing message for thread {task_id}")

    # Echo the user's message into the task history.
    await adk.messages.create(task_id=task_id, content=params.event.content)

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
            final_output = await stream_pydantic_ai_events(stream, task_id, tracing_handler=tracing_handler)

        if turn_span:
            turn_span.output = {"final_output": final_output}


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    logger.info(f"Task created: {params.task.id}")


@acp.on_task_cancel
async def handle_task_canceled(params: CancelTaskParams):
    logger.info(f"Task canceled: {params.task.id}")
