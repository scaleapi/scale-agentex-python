"""
ACP (Agent Communication Protocol) handler for Agentex.

This is the API layer — it manages the graph lifecycle and streams
tokens and tool calls from the LangGraph graph to the Agentex frontend.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

import agentex.lib.adk as adk
from project.graph import create_graph
from agentex.lib.adk import create_langgraph_tracing_handler, convert_langgraph_to_agentex_events
from agentex.lib.types.acp import SendMessageParams
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import TaskMessageUpdate
from agentex.types.task_message_content import TaskMessageContent
from agentex.lib.core.tracing.tracing_processor_manager import add_tracing_processor_config

logger = make_logger(__name__)

# Register the Agentex tracing processor so spans are shipped to the backend
add_tracing_processor_config(
    SGPTracingProcessorConfig(
        sgp_api_key=os.environ.get("SGP_API_KEY", ""),
        sgp_account_id=os.environ.get("SGP_ACCOUNT_ID", ""),
        sgp_base_url=os.environ.get("SGP_CLIENT_BASE_URL", ""),
    ))
# Create ACP server
acp = FastACP.create(acp_type="sync")

# Compiled graph (lazy-initialized on first request)
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
    """Handle incoming messages from Agentex, streaming tokens and tool calls."""
    graph = await get_graph()

    thread_id = params.task.id
    user_message = params.content.content

    logger.info(f"Processing message for thread {thread_id}")

    async with adk.tracing.span(
        trace_id=thread_id,
        name="message",
        input={"message": user_message},
        data={"__span_type__": "AGENT_WORKFLOW"},
    ) as turn_span:
        callback = create_langgraph_tracing_handler(
            trace_id=thread_id,
            parent_span_id=turn_span.id if turn_span else None,
        )

        stream = graph.astream(
            {"messages": [{"role": "user", "content": user_message}]},
            config={
                "configurable": {"thread_id": thread_id},
                "callbacks": [callback],
            },
            stream_mode=["messages", "updates"],
        )

        final_text = ""
        async for event in convert_langgraph_to_agentex_events(stream):
            # Accumulate text deltas for span output
            delta = getattr(event, "delta", None)
            if isinstance(delta, TextDelta) and delta.text_delta:
                final_text += delta.text_delta
            yield event

        if turn_span:
            turn_span.output = {"final_output": final_text}
