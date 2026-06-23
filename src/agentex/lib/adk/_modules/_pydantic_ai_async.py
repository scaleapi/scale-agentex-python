"""Async Pydantic AI streaming helper for Agentex.

Consumes a Pydantic AI ``agent.run_stream_events(...)`` async iterator and
pushes Agentex streaming updates to Redis via the ``adk.streaming``
contexts. For use with async ACP agents that stream via Redis rather than
HTTP yields.

Text and thinking tokens stream as deltas inside coalesced streaming
contexts. Tool requests and tool results are posted as open+close pairs
on a streaming context (the unified surface persists ``initial_content``
when a context is closed without deltas). This matches the ``auto_send``
convention used by all other async/Temporal harnesses.

Tracing is opt-in via a ``tracing_handler`` parameter — see
``create_pydantic_ai_tracing_handler`` in
``agentex.lib.adk._modules._pydantic_ai_tracing``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentex.lib.adk._modules._pydantic_ai_tracing import (
        AgentexPydanticAITracingHandler,
    )


async def stream_pydantic_ai_events(
    stream,
    task_id: str,
    tracing_handler: "AgentexPydanticAITracingHandler | None" = None,
) -> str:
    """Stream Pydantic AI events to Agentex via Redis.

    Args:
        stream: Async iterator yielded by ``agent.run_stream_events(...)``.
        task_id: The Agentex task ID to stream messages to.
        tracing_handler: Optional handler from
            ``create_pydantic_ai_tracing_handler(...)``. When provided, each
            tool call in the run is also recorded as an Agentex child span
            beneath the handler's configured ``parent_span_id``. Streaming
            behavior is unchanged when omitted.

    Returns:
        The accumulated text content of the **last** text part in the run.
        Multi-step runs (where the model emits text, then a tool call, then
        more text) return only the final text segment, matching the
        ``stream_langgraph_events`` convention.
    """
    from agentex.lib.core.harness.emitter import UnifiedEmitter
    from agentex.lib.adk._modules._pydantic_ai_turn import PydanticAITurn

    turn = PydanticAITurn(
        stream,
        model=None,
        tracing_handler=tracing_handler,
    )
    emitter = UnifiedEmitter(
        task_id=task_id,
        trace_id=None,
        parent_span_id=None,
    )
    result = await emitter.auto_send_turn(turn)
    return result.final_text
