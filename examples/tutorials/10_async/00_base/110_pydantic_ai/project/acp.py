"""ACP handler for the async harness Pydantic AI test agent.

This agent exercises the UNIFIED HARNESS SURFACE on the async (Redis-streaming)
channel — ``UnifiedEmitter.auto_send_turn(PydanticAITurn(...))``
— calling it directly rather than via the ``stream_pydantic_ai_events`` helper
(which the ``110_pydantic_ai`` tutorial uses). This makes the unified-surface
wiring explicit at the agent-author level.

Multi-turn memory is persisted via ``adk.state``: on each turn we load the
previous pydantic-ai ``message_history`` from state, run the agent with it,
then save the updated history back.
"""

from __future__ import annotations

import os
from typing import Any, AsyncIterator

from dotenv import load_dotenv

load_dotenv()

from pydantic_ai.run import AgentRunResultEvent
from pydantic_ai.messages import ModelMessagesTypeAdapter

import agentex.lib.adk as adk
from project.agent import MODEL_NAME, create_agent
from agentex.lib.types.acp import SendEventParams, CancelTaskParams, CreateTaskParams
from agentex.lib.core.harness import UnifiedEmitter
from agentex.lib.types.fastacp import AsyncACPConfig
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.sdk.fastacp.fastacp import FastACP
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
    ``ModelMessage`` objects through JSON.
    """

    history_json: str = "[]"
    turn_number: int = 0


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    """Initialize per-task state on task creation."""
    logger.info(f"Task created: {params.task.id}")
    await adk.state.create(
        task_id=params.task.id,
        agent_id=params.agent.id,
        state=ConversationState(),
    )


@acp.on_task_event_send
async def handle_task_event_send(params: SendEventParams):
    """Handle each user message through the unified auto_send_turn path."""
    agent = get_agent()
    task_id = params.task.id
    agent_id = params.agent.id
    user_message = params.event.content.content

    logger.info(f"Processing message for thread {task_id}")

    # Echo the user's message into the task history.
    await adk.messages.create(task_id=task_id, content=params.event.content)

    # Load the previous conversation history from state (fall back to fresh).
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
        # Construct the UnifiedEmitter from the ACP context so tracing is
        # automatic and messages are auto-sent to the task stream (Redis).
        emitter = UnifiedEmitter(
            task_id=task_id,
            trace_id=task_id,
            parent_span_id=turn_span.id if turn_span else None,
        )

        # Capture the terminal AgentRunResultEvent to persist message history.
        captured_messages: list[Any] = []

        async def tee_messages(upstream) -> AsyncIterator[Any]:
            async for event in upstream:
                if isinstance(event, AgentRunResultEvent):
                    captured_messages[:] = list(event.result.all_messages())
                yield event

        async with agent.run_stream_events(user_message, message_history=previous_messages) as stream:
            # The unified auto_send path delivers streamed tool requests natively
            # (Start+Delta+Done), so no coalescing workaround is needed.
            turn = PydanticAITurn(
                tee_messages(stream),
                model=MODEL_NAME,
            )
            result = await emitter.auto_send_turn(turn)

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
            turn_span.output = {"final_output": result.final_text}


@acp.on_task_cancel
async def handle_task_canceled(params: CancelTaskParams):
    logger.info(f"Task canceled: {params.task.id}")
