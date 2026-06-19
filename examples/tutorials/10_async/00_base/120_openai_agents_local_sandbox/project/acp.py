"""ACP handler for the async OpenAI Agents SDK local-sandbox agent.

Uses the async ACP model (``acp_type: async``, ``temporal.enabled: false``),
mirroring the Pydantic AI tutorial (110). The difference is the runtime: here we
run an OpenAI Agents SDK ``SandboxAgent`` against the **local** sandbox backend
(``UnixLocalSandboxClient``), which executes real shell commands on the host.

The OpenAI Agents SDK sandbox runtime drives the full tool-call loop internally
inside ``Runner.run`` (model -> shell command -> output -> model -> ... -> final
answer), so this handler runs the agent and persists a single final
``TextContent`` rather than streaming tokens itself.

Multi-turn memory is persisted via ``adk.state``: on each turn we load the prior
OpenAI Agents SDK input list from state, run the agent with it, then save the
updated list (``result.to_input_list()``) back. Without this, every turn would be
a fresh stateless run and the agent would forget the prior conversation.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

import agentex.lib.adk as adk
from project.agent import run_agent
from agentex.lib.types.acp import SendEventParams, CancelTaskParams, CreateTaskParams
from agentex.lib.types.fastacp import AsyncACPConfig
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.sdk.fastacp.fastacp import FastACP
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

acp = FastACP.create(
    acp_type="async",
    config=AsyncACPConfig(type="base"),
)


class ConversationState(BaseModel):
    """Per-task conversation state persisted via ``adk.state``.

    ``input_list`` holds the OpenAI Agents SDK conversation history — the same
    structure ``Runner.run`` accepts as input and ``result.to_input_list()``
    returns. Persisting it between turns gives the agent multi-turn memory.
    """

    input_list: list[dict[str, Any]] = []
    turn_number: int = 0


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    """Initialize per-task state on task creation.

    A fresh task starts with no message history; the conversation is built up by
    ``handle_task_event_send`` on each subsequent user message.
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
    task_id = params.task.id
    agent_id = params.agent.id
    user_message = params.event.content.content

    logger.info(f"Processing message for thread {task_id}")

    # Echo the user's message into the task history so it shows up in the UI.
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
    state.input_list.append({"role": "user", "content": user_message})

    async with adk.tracing.span(
        trace_id=task_id,
        task_id=task_id,
        name=f"Turn {state.turn_number}",
        input={"message": user_message},
        data={"__span_type__": "AGENT_WORKFLOW"},
    ) as turn_span:
        # The OpenAI Agents SDK sandbox runtime runs the full tool-call loop
        # internally (model -> shell command on the local host -> output ->
        # model -> ... -> final answer), so we get a single final result.
        result = await run_agent(state.input_list)
        final_output = result.final_output

        # Persist the assistant's final answer as a TaskMessage so it shows up
        # in the UI. (Unlike the streaming Pydantic AI tutorial, the sandbox run
        # is non-streaming, so we post the final text ourselves.)
        await adk.messages.create(
            task_id=task_id,
            content=TextContent(author="agent", content=final_output),
        )

        # Save the updated message history so the next turn picks up here.
        state.input_list = result.to_input_list()
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
