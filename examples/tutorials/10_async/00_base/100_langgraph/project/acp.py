"""ACP handler for the async LangGraph agent.

Uses the unified harness surface: ``LangGraphTurn`` wraps the LangGraph
``astream()`` generator, and ``UnifiedEmitter.auto_send_turn`` streams events
to Redis and returns a ``TurnResult`` with the accumulated final text.

Properties of the unified surface:
- Tracing is wired through the tracing manager (no bespoke handler boilerplate).
- A single ``UnifiedEmitter.auto_send_turn(LangGraphTurn(stream))`` call
  replaces bespoke event-streaming helpers.
- Tool calls/responses go through ``streaming_task_message_context``
  (same code path as text deltas), making the event stream channel-agnostic.
- Usage data (token counts) is captured on ``LangGraphTurn.usage()`` after
  ``auto_send_turn`` returns.

AGX1-377 note: LangGraph emits tool requests as ``StreamTaskMessageFull``
events (from "updates"). The ``SpanDeriver`` does not open tool spans from
Full events today; that gap is tracked in AGX1-373.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

import agentex.lib.adk as adk
from project.graph import create_graph
from agentex.lib.types.acp import SendEventParams, CancelTaskParams, CreateTaskParams
from agentex.lib.types.fastacp import AsyncACPConfig
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.core.harness.emitter import UnifiedEmitter
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

acp = FastACP.create(
    acp_type="async",
    config=AsyncACPConfig(type="base"),
)

_graph = None


async def get_graph():
    global _graph
    if _graph is None:
        _graph = await create_graph()
    return _graph


@acp.on_task_event_send
async def handle_task_event_send(params: SendEventParams):
    """Handle incoming events, streaming tokens and tool calls via unified harness."""
    graph = await get_graph()
    task_id = params.task.id
    user_message = params.event.content.content

    logger.info(f"Processing message for thread {task_id}")

    await adk.messages.create(task_id=task_id, content=params.event.content)

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

        result = await emitter.auto_send_turn(turn)

        if turn_span:
            turn_span.output = {"final_output": result.final_text}


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    logger.info(f"Task created: {params.task.id}")


@acp.on_task_cancel
async def handle_task_canceled(params: CancelTaskParams):
    logger.info(f"Task canceled: {params.task.id}")
