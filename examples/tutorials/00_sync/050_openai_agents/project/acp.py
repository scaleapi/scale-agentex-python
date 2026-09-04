"""ACP handler for the sync OpenAI Agents harness tutorial.

This is the API layer. It runs the OpenAI Agents SDK via ``Runner.run_streamed``,
wraps the streamed run in an ``OpenAITurn`` (the provider -> canonical
``StreamTaskMessage*`` adapter), and forwards the canonical stream to the
Agentex frontend via ``UnifiedEmitter.yield_turn`` — the same harness surface
used by the async and temporal variants of this tutorial.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

from agents import Runner

from agentex.lib import adk
from project.agent import MODEL_NAME, create_agent
from agentex.lib.types.acp import SendMessageParams
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.task_message_update import TaskMessageUpdate
from agentex.types.task_message_content import TaskMessageContent
from agentex.lib.adk.providers._modules.openai_turn import OpenAITurn
from agentex.lib.core.tracing.tracing_processor_manager import add_tracing_processor_config

logger = make_logger(__name__)

# LiteLLM proxy auth: copy LITELLM_API_KEY to OPENAI_API_KEY for OpenAI client
# compatibility, so the same example works behind the Scale LiteLLM gateway.
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

acp = FastACP.create(acp_type="sync")

_agent = None


def get_agent():
    """Get or create the OpenAI Agents SDK agent instance."""
    global _agent
    if _agent is None:
        _agent = create_agent()
    return _agent


@acp.on_message_send
async def handle_message_send(
    params: SendMessageParams,
) -> TaskMessageContent | list[TaskMessageContent] | AsyncGenerator[TaskMessageUpdate, None]:
    """Handle incoming messages, streaming tokens and tool calls via the harness."""
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
        result = Runner.run_streamed(starting_agent=agent, input=user_message)
        turn = OpenAITurn(result=result, model=MODEL_NAME)
        emitter = UnifiedEmitter(
            task_id=task_id,
            trace_id=task_id,
            parent_span_id=turn_span.id if turn_span else None,
        )
        async for event in emitter.yield_turn(turn):
            yield event
