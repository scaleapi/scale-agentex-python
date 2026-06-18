"""ACP handler for sync harness LangGraph agent.

Uses the unified harness surface: ``LangGraphTurn`` wraps the LangGraph
``astream()`` generator, and ``UnifiedEmitter.yield_turn`` converts it into
the AgentEx ``TaskMessageUpdate`` event stream expected by the sync ACP.

Differences from ``030_langgraph`` (bespoke path):
- No ``create_langgraph_tracing_handler`` boilerplate.
- No manual text-delta accumulation for the span output.
- Tool calls are emitted as ``StreamTaskMessageFull`` (not Start+Delta+Done)
  via the same code path as the async/temporal channels.
- Usage data (token counts) is captured on the ``LangGraphTurn`` object and
  can be read after the turn completes.

AGX1-377 note: LangGraph emits tool requests as ``StreamTaskMessageFull``
events (from "updates"). The ``SpanDeriver`` does not open tool spans from
Full events today; that gap is tracked in AGX1-373.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

import agentex.lib.adk as adk
from project.graph import create_graph
from agentex.lib.types.acp import SendMessageParams
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.task_message_update import TaskMessageUpdate
from agentex.types.task_message_content import TaskMessageContent
from agentex.lib.adk._modules._langgraph_turn import LangGraphTurn
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

_graph = None


async def get_graph():
    """Get or create the compiled graph instance."""
    global _graph
    if _graph is None:
        _graph = await create_graph()
    return _graph


@acp.on_message_send
async def handle_message_send(
    params: SendMessageParams,
) -> TaskMessageContent | list[TaskMessageContent] | AsyncGenerator[TaskMessageUpdate, None]:
    """Handle incoming messages, streaming tokens and tool calls via unified harness."""
    graph = await get_graph()

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
        stream = graph.astream(
            {"messages": [{"role": "user", "content": user_message}]},
            config={"configurable": {"thread_id": task_id}},
            stream_mode=["messages", "updates"],
        )

        turn = LangGraphTurn(stream, model=None)
        emitter = UnifiedEmitter(
            task_id=task_id,
            trace_id=task_id,
            parent_span_id=turn_span.id if turn_span else None,
        )

        async for event in emitter.yield_turn(turn):
            yield event

        if turn_span:
            turn_span.output = {"final_output": turn.usage().model_dump()}
