"""Pydantic AI agent definition for the Temporal harness test agent.

This module constructs the base ``pydantic_ai.Agent`` once at import time,
registers tools on it, and wraps it in ``TemporalAgent`` from
``pydantic_ai.durable_exec.temporal``.

The ``TemporalAgent`` wrapper makes every model call and every tool call run as
a Temporal activity automatically. The workflow stays deterministic; the
non-deterministic work (LLM HTTP calls, tool execution) moves into recorded
activities.

Streaming back to Agentex happens via ``event_stream_handler``, which receives
Pydantic AI ``AgentStreamEvent``s from inside the model activity and forwards
them through the UNIFIED HARNESS SURFACE (``UnifiedEmitter.auto_send_turn`` +
``PydanticAITurn``) — called directly rather than via ``stream_pydantic_ai_events``.
The ``task_id`` and per-turn ``parent_span_id`` are threaded into the handler
via ``deps``.
"""

from __future__ import annotations

from datetime import datetime
from collections.abc import AsyncIterable

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import AgentStreamEvent
from pydantic_ai.durable_exec.temporal import TemporalAgent

from project.tools import get_weather
from agentex.lib.core.harness import UnifiedEmitter
from agentex.lib.adk._modules._pydantic_ai_turn import PydanticAITurn

__all__ = ["TaskDeps", "temporal_agent", "base_agent", "MODEL_NAME"]

MODEL_NAME = "openai:gpt-4o-mini"
SYSTEM_PROMPT = """You are a helpful AI assistant with access to tools.

Current date and time: {timestamp}

Guidelines:
- Be concise and helpful
- Use tools when they would help answer the user's question
- If you're unsure, ask clarifying questions
- Always provide accurate information
"""


class TaskDeps(BaseModel):
    """Per-run dependencies passed into the agent via ``deps=``.

    Pydantic AI's ``RunContext.deps`` is the canonical place to thread
    request-scoped data (like the Agentex task_id) into tools and event
    handlers — including code that runs inside Temporal activities.
    """

    task_id: str
    # When set, the event handler nests per-tool-call spans under this span.
    # Typically the ID of the per-turn span opened by the workflow.
    parent_span_id: str | None = None


def _build_base_agent() -> Agent[TaskDeps, str]:
    """Build the underlying Pydantic AI agent with tools registered.

    Tools must be registered BEFORE the agent is wrapped in TemporalAgent;
    changes to tool registration after wrapping are not reflected.
    """
    agent: Agent[TaskDeps, str] = Agent(
        MODEL_NAME,
        deps_type=TaskDeps,
        system_prompt=SYSTEM_PROMPT.format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    agent.tool_plain(get_weather)
    return agent


async def event_handler(
    run_context: RunContext[TaskDeps],
    events: AsyncIterable[AgentStreamEvent],
) -> None:
    """Stream Pydantic AI events to Agentex via the unified surface.

    Pydantic AI calls this with the live event stream as soon as the model
    activity begins emitting parts. Because the handler runs inside the activity
    (not the workflow), it can freely make non-deterministic Redis + tracing
    writes.

    The UnifiedEmitter is constructed from ``deps`` (task_id + parent_span_id),
    so tool spans nest under the workflow's per-turn span and messages auto-send
    to the task stream. The auto_send path delivers streamed tool requests
    natively, so no coalescing workaround is needed.
    """
    emitter = UnifiedEmitter(
        task_id=run_context.deps.task_id,
        trace_id=run_context.deps.task_id,
        parent_span_id=run_context.deps.parent_span_id,
    )
    turn = PydanticAITurn(events, model=MODEL_NAME)
    await emitter.auto_send_turn(turn)


# Construct the durable agent at module load time so that the PydanticAIPlugin
# can auto-discover its activities via the workflow's ``__pydantic_ai_agents__``
# attribute.
base_agent = _build_base_agent()
temporal_agent: TemporalAgent[TaskDeps, str] = TemporalAgent(
    base_agent,
    name="pydantic_ai_agent",
    event_stream_handler=event_handler,
)
