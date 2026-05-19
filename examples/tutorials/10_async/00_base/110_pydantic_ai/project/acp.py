"""ACP handler for async Pydantic AI agent.

Uses the async ACP model with Redis streaming instead of HTTP yields.
Text and reasoning tokens stream as Redis deltas; tool requests and
responses are persisted as discrete full messages.

Multi-turn memory is persisted via ``adk.state``: on each turn we load the
previous pydantic-ai ``message_history`` from state, run the agent with it,
then save the updated history back. Without this, every turn would be a
fresh stateless run and the agent would forget the prior conversation.
"""

from __future__ import annotations

import os
from typing import Any, AsyncIterator

from dotenv import load_dotenv

load_dotenv()

from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.run import AgentRunResultEvent

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
from agentex.lib.utils.model_utils import BaseModel
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


class ConversationState(BaseModel):
    """Per-task conversation state persisted via ``adk.state``.

    ``history_json`` holds the pydantic-ai message history serialized by
    ``ModelMessagesTypeAdapter`` — pydantic-ai's official way to round-trip
    ``ModelMessage`` objects through JSON. We can't use a plain
    ``list[ModelMessage]`` field because ``ModelMessage`` is a discriminated
    union of runtime types, not a stable Pydantic schema.
    """

    history_json: str = "[]"
    turn_number: int = 0


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    """Initialize per-task state on task creation.

    A fresh task starts with no message history; the conversation is built
    up by ``handle_task_event_send`` on each subsequent user message.
    """
    logger.info(f"Task created: {params.task.id}")
    await adk.state.create(
        task_id=params.task.id,
        agent_id=params.agent.id,
        state=ConversationState(),
    )


@acp.on_task_event_send
async def handle_task_event_send(params: SendEventParams):
    """Handle each user message: load prior history, run the agent, save updated history."""
    agent = get_agent()
    task_id = params.task.id
    agent_id = params.agent.id
    user_message = params.event.content.content

    logger.info(f"Processing message for thread {task_id}")

    # Echo the user's message into the task history.
    await adk.messages.create(task_id=task_id, content=params.event.content)

    # Load the previous conversation history from state. If state is missing
    # (e.g. task wasn't initialised via on_task_create), fall back to a fresh
    # one so the agent still responds — just without memory of prior turns.
    task_state = await adk.state.get_by_task_and_agent(task_id=task_id, agent_id=agent_id)
    if task_state is None:
        state = ConversationState()
        task_state = await adk.state.create(task_id=task_id, agent_id=agent_id, state=state)
    else:
        state = ConversationState.model_validate(task_state.state)

    state.turn_number += 1
    previous_messages = ModelMessagesTypeAdapter.validate_json(state.history_json)

    async with adk.tracing.span(
        trace_id=task_id,
        task_id=task_id,
        name=f"Turn {state.turn_number}",
        input={"message": user_message},
        data={"__span_type__": "AGENT_WORKFLOW"},
    ) as turn_span:
        tracing_handler = create_pydantic_ai_tracing_handler(
            trace_id=task_id,
            parent_span_id=turn_span.id if turn_span else None,
            task_id=task_id,
        )

        # Wrap the pydantic-ai event stream so we can capture the final
        # AgentRunResultEvent (which carries the full message list for the
        # next turn) without changing the streaming-helper's signature.
        captured_messages: list[Any] = []

        async def tee_messages(upstream) -> AsyncIterator[Any]:
            async for event in upstream:
                if isinstance(event, AgentRunResultEvent):
                    captured_messages[:] = list(event.result.all_messages())
                yield event

        async with agent.run_stream_events(
            user_message, message_history=previous_messages
        ) as stream:
            final_output = await stream_pydantic_ai_events(
                tee_messages(stream), task_id, tracing_handler=tracing_handler
            )

        # Save the updated message history so the next turn picks up here.
        if captured_messages:
            state.history_json = ModelMessagesTypeAdapter.dump_json(captured_messages).decode()
            await adk.state.update(
                state_id=task_state.id,
                task_id=task_id,
                agent_id=agent_id,
                state=state,
            )

        if turn_span:
            turn_span.output = {"final_output": final_output}


@acp.on_task_cancel
async def handle_task_canceled(params: CancelTaskParams):
    logger.info(f"Task canceled: {params.task.id}")
