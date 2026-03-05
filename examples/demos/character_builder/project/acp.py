"""FastACP server for the D&D character builder multi-agent demo."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from agentex.lib import adk
from agentex.lib.adk.providers._modules.sync_provider import SyncStreamingProvider
from agentex.lib.core.tracing.tracing_processor_manager import add_tracing_processor_config
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agents import Runner

from project.agents import BuilderContext, build_agents
from project.models import CharacterSheet, StateModel, Step
from project.streaming import stream_agent_events

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from agentex.lib.types.acp import SendMessageParams
    from agentex.types.task_message_content import TaskMessageContent
    from agentex.types.task_message_update import TaskMessageUpdate

logger = make_logger(__name__)

MODEL_NAME = "gpt-4o-mini"

# ── Tracing ─────────────────────────────────────────────────────────────────────────────────────────

SGP_API_KEY = os.environ.get("SGP_API_KEY", "")
SGP_ACCOUNT_ID = os.environ.get("SGP_ACCOUNT_ID", "")

if SGP_API_KEY and SGP_ACCOUNT_ID:
    add_tracing_processor_config(SGPTracingProcessorConfig(sgp_api_key=SGP_API_KEY, sgp_account_id=SGP_ACCOUNT_ID))

# ── ACP server ──────────────────────────────────────────────────────────────────────────────────────

acp = FastACP.create(acp_type="sync")


@acp.on_message_send
async def handle_message_send(
    params: SendMessageParams,
) -> TaskMessageContent | list[TaskMessageContent] | AsyncGenerator[TaskMessageUpdate, None]:
    """Handle an incoming user message and stream agent responses."""
    user_prompt = params.content.content

    # Restore or create persisted state
    task_state = await adk.state.get_by_task_and_agent(task_id=params.task.id, agent_id=params.agent.id)

    # Build agents with a concrete Model instance so all agents share it across handoffs.
    provider = SyncStreamingProvider(trace_id=params.task.id)
    orchestrator, agents_by_name = build_agents(provider.get_model(MODEL_NAME))

    if not task_state:
        state = StateModel(input_list=[], sheet={}, steps=[], last_agent_name=orchestrator.name)
        task_state = await adk.state.create(task_id=params.task.id, agent_id=params.agent.id, state=state)
    else:
        state = StateModel.model_validate(task_state.state)

    # Reconstruct BuilderContext from persisted state
    sheet = CharacterSheet.model_validate(state.sheet) if state.sheet else CharacterSheet()
    steps = [Step.model_validate(s) for s in state.steps] if state.steps else None
    builder_ctx = BuilderContext(sheet=sheet, steps=steps) if steps is not None else BuilderContext(sheet=sheet)

    starting_agent = agents_by_name.get(state.last_agent_name, orchestrator)
    state.input_list.append({"role": "user", "content": user_prompt})

    result = Runner.run_streamed(
        starting_agent=starting_agent,
        input=state.input_list,
        context=builder_ctx,
        max_turns=25,
    )

    async for agentex_event in stream_agent_events(result.stream_events()):
        yield agentex_event

    # Persist updated state
    state.input_list = result.to_input_list()
    state.sheet = builder_ctx.sheet.model_dump()
    state.steps = [s.model_dump() for s in builder_ctx.steps]
    state.last_agent_name = result.last_agent.name

    await adk.state.update(
        state_id=task_state.id,
        task_id=params.task.id,
        agent_id=params.agent.id,
        state=state,
        trace_id=params.task.id,
    )
