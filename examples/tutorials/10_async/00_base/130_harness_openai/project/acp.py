"""ACP handler for the async OpenAI Agents harness tutorial.

Uses the async ACP model with Redis streaming instead of HTTP yields. The
OpenAI Agents SDK run is wrapped in an ``OpenAITurn`` and pushed to the task
stream via ``UnifiedEmitter.auto_send_turn`` — the async/temporal delivery path
of the unified harness surface. ``auto_send_turn`` returns a ``TurnResult``
carrying the accumulated final text and normalized usage.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from agents import Runner

from agentex.lib import adk
from project.agent import MODEL_NAME, create_agent
from agentex.lib.types.acp import SendEventParams, CancelTaskParams, CreateTaskParams
from agentex.lib.types.fastacp import AsyncACPConfig
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.lib.adk.providers._modules.openai_turn import OpenAITurn
from agentex.lib.core.tracing.tracing_processor_manager import add_tracing_processor_config

logger = make_logger(__name__)

_litellm_key = os.environ.get("LITELLM_API_KEY")
if _litellm_key and not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = _litellm_key

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


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    logger.info(f"Task created: {params.task.id}")


@acp.on_task_event_send
async def handle_task_event_send(params: SendEventParams):
    """Handle each user message: run the agent and auto-send its turn."""
    agent = get_agent()
    task_id = params.task.id
    user_message = params.event.content.content

    logger.info(f"Processing message for task {task_id}")

    # Echo the user's message into the task history.
    await adk.messages.create(task_id=task_id, content=params.event.content)

    async with adk.tracing.span(
        trace_id=task_id,
        task_id=task_id,
        name="message",
        input={"message": user_message},
        data={"__span_type__": "AGENT_WORKFLOW"},
    ) as turn_span:
        result = Runner.run_streamed(starting_agent=agent, input=user_message)
        turn = OpenAITurn(result=result, model=MODEL_NAME)
        emitter = UnifiedEmitter(
            task_id=task_id,
            trace_id=task_id,
            parent_span_id=turn_span.id if turn_span else None,
        )
        turn_result = await emitter.auto_send_turn(turn)
        if turn_span:
            turn_span.output = {"final_output": turn_result.final_text}


@acp.on_task_cancel
async def handle_task_canceled(params: CancelTaskParams):
    logger.info(f"Task canceled: {params.task.id}")
