"""Async LangGraph streaming helper for Agentex.

Converts LangGraph graph.astream() events into Agentex streaming updates
and pushes them to Redis via adk.streaming contexts. For use with async
ACP agents that stream via Redis rather than HTTP yields.

Unified surface
---------------
This module is now implemented on top of ``LangGraphTurn`` and
``UnifiedEmitter.auto_send_turn``, the same surface used by every other
harness adapter (pydantic-ai, openai-agents, etc.). The public signature
and return type are preserved identically.

AGX1-377 note: LangGraph emits tool requests as ``StreamTaskMessageFull`` events
(from "updates" events), NOT Start+Delta+Done like pydantic-ai. ``auto_send``
handles Full events correctly; no coalescing wrapper is needed.
"""

from agentex.lib.utils.temporal import workflow_now_if_in_workflow


async def stream_langgraph_events(stream, task_id: str) -> str:
    """Stream LangGraph events to Agentex via Redis.

    Processes the stream from graph.astream() called with
    stream_mode=["messages", "updates"] and pushes text, reasoning,
    tool request, and tool response messages through Redis streaming
    contexts.

    Supports both regular models (chunk.content is a str) and reasoning
    models like gpt-5/o1/o3 (chunk.content is a list of typed content blocks
    in the Responses API responses/v1 format).

    Reimplemented on ``UnifiedEmitter.auto_send_turn(LangGraphTurn(...))`` for
    cross-harness consistency. Behavior is identical to the previous bespoke
    implementation (verified by characterization tests in test_langgraph_async.py).

    AGX1-377 note: LangGraph emits tool requests as ``Full`` events (from "updates"),
    NOT Start+Delta+Done like pydantic-ai. ``auto_send`` handles Full events
    correctly; no coalescing wrapper is needed.

    AGX1-378 note: ``created_at`` is set from ``workflow.now()`` when called inside a
    Temporal workflow, matching the pattern used by the openai/litellm providers.
    Outside a workflow (plain async activities, sync agents) it is ``None`` and the
    server's wall clock is used.

    Args:
        stream: Async iterator from graph.astream(..., stream_mode=["messages", "updates"])
        task_id: The Agentex task ID to stream messages to.

    Returns:
        The accumulated final text output from the agent.
    """
    from agentex.lib.core.harness.emitter import UnifiedEmitter
    from agentex.lib.adk._modules._langgraph_turn import LangGraphTurn

    # AGX1-377 note: LangGraph emits tool requests as Full events (from "updates"),
    # NOT Start+Delta+Done like pydantic-ai. auto_send handles Full events correctly;
    # no coalescing wrapper is needed.
    # AGX1-378: stamp messages with workflow.now() inside Temporal for deterministic
    # created_at ordering; falls back to None (server wall clock) outside a workflow.
    turn = LangGraphTurn(stream, model=None)
    emitter = UnifiedEmitter(task_id=task_id, trace_id=None, parent_span_id=None)
    result = await emitter.auto_send_turn(turn, created_at=workflow_now_if_in_workflow())
    return result.final_text
