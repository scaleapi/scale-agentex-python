"""ACP handler for the sync harness Pydantic AI test agent.

This agent exercises the UNIFIED HARNESS SURFACE on the sync (HTTP-yield)
channel — ``UnifiedEmitter.yield_turn(PydanticAITurn(...))`` — rather than the
bare ``convert_pydantic_ai_to_agentex_events`` converter used by the
``040_pydantic_ai`` tutorial. The unified surface gives the sync channel the
same tracing (span derivation) the async/temporal channels get for free.

Flow:
1. Open a per-turn AGENT_WORKFLOW span via ``adk.tracing.span``.
2. Construct a ``UnifiedEmitter`` from the ACP/streaming context (task_id +
   trace_id + parent_span_id) so tool spans nest under the turn span.
3. Wrap ``agent.run_stream_events(...)`` in a ``PydanticAITurn`` and forward
   events with ``emitter.yield_turn(turn)`` — yielding each to the client.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

import agentex.lib.adk as adk
from project.agent import MODEL_NAME, create_agent
from agentex.lib.types.acp import SendMessageParams
from agentex.lib.core.harness import UnifiedEmitter
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.types.task_message_update import TaskMessageUpdate
from agentex.types.task_message_content import TaskMessageContent
from agentex.lib.adk._modules._pydantic_ai_turn import PydanticAITurn
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
    """Handle incoming messages, streaming events through the unified surface."""
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
        # Construct the UnifiedEmitter from the ACP/streaming context so tracing
        # is automatic: tool spans nest under this turn's span.
        emitter = UnifiedEmitter(
            task_id=task_id,
            trace_id=task_id,
            parent_span_id=turn_span.id if turn_span else None,
        )

        async with agent.run_stream_events(user_message) as stream:
            # PydanticAITurn preserves token-by-token tool-call argument
            # streaming (Start+Delta+Done) on the sync/HTTP channel.
            turn = PydanticAITurn(stream, model=MODEL_NAME)
            async for ev in emitter.yield_turn(turn):
                yield ev
