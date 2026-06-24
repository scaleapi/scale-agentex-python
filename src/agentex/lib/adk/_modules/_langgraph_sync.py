"""Sync LangGraph streaming helper for Agentex.

Converts LangGraph graph.astream() events into Agentex TaskMessageUpdate
events that are yielded back over the HTTP response. For use with sync ACP
agents that stream via HTTP yields rather than Redis.

Unified sync path
-----------------
Prefer using ``LangGraphTurn`` with ``UnifiedEmitter.yield_turn`` for new
agents, which adds usage capture and optional tracing via the shared harness
surface::

    from agentex.lib.core.harness.emitter import UnifiedEmitter
    from agentex.lib.adk._modules._langgraph_turn import LangGraphTurn

    turn = LangGraphTurn(stream)
    emitter = UnifiedEmitter(task_id=task_id, trace_id=trace_id, parent_span_id=span_id)
    async for event in emitter.yield_turn(turn):
        yield event

``convert_langgraph_to_agentex_events`` remains available as a lower-level
primitive (e.g. for callers that need the raw event stream without the
harness envelope).
"""

from __future__ import annotations

from typing import Any, Callable, Optional
from collections.abc import AsyncGenerator


async def convert_langgraph_to_agentex_events(
    stream: Any,
    on_final_ai_message: Optional[Callable[..., None]] = None,
) -> AsyncGenerator[Any, None]:
    """Convert LangGraph streaming events to Agentex TaskMessageUpdate events.

    Expects the stream from graph.astream() called with
    stream_mode=["messages", "updates"]. This produces two event types:

      ("messages", (message_chunk, metadata))  — token-by-token LLM output
      ("updates", {node_name: state_update})   — complete node outputs

    Text tokens are streamed as Start/Delta/Done sequences.
    Reasoning tokens are streamed as Start/Delta/Done sequences with ReasoningContentDelta.
    Tool calls and tool results are emitted as Full messages.

    Supports both regular models (chunk.content is a str) and reasoning models
    like gpt-5/o1/o3 (chunk.content is a list of typed content blocks).

    LangGraph emits tool requests as ``StreamTaskMessageFull`` (from "updates"
    events), NOT Start+Delta+Done like pydantic-ai. No coalesce_tool_requests
    option is needed for LangGraph.

    Args:
        stream: Async iterator from graph.astream(..., stream_mode=["messages", "updates"])
        on_final_ai_message: Optional callback ``(msg: AIMessage) -> None`` called for
            each ``AIMessage`` in an "agent" node update. Use this to capture
            ``usage_metadata`` for token accounting without re-traversing the stream.
            The callback fires *after* all events for that message are yielded.
            No-op when ``None`` (default).

    Yields:
        TaskMessageUpdate events (Start, Delta, Done, Full)
    """
    # Lazy imports so langgraph/langchain aren't required at module load time
    from langchain_core.messages import ToolMessage, AIMessageChunk

    from agentex.types.text_content import TextContent
    from agentex.types.reasoning_content import ReasoningContent
    from agentex.types.task_message_delta import TextDelta
    from agentex.types.task_message_update import (
        StreamTaskMessageDone,
        StreamTaskMessageFull,
        StreamTaskMessageDelta,
        StreamTaskMessageStart,
    )
    from agentex.types.tool_request_content import ToolRequestContent
    from agentex.types.tool_response_content import ToolResponseContent
    from agentex.types.reasoning_content_delta import ReasoningContentDelta
    from agentex.types.reasoning_summary_delta import ReasoningSummaryDelta

    message_index = 0
    text_streaming = False
    reasoning_streaming = False
    reasoning_content_index = 0

    async for event_type, event_data in stream:
        if event_type == "messages":
            chunk, metadata = event_data

            if not isinstance(chunk, AIMessageChunk) or not chunk.content:
                continue

            # ----------------------------------------------------------
            # Case 1: content is a plain string (regular models)
            # ----------------------------------------------------------
            if isinstance(chunk.content, str):
                # Close reasoning stream if we're transitioning to text
                if reasoning_streaming:
                    yield StreamTaskMessageDone(type="done", index=message_index)
                    reasoning_streaming = False
                    message_index += 1

                if not text_streaming:
                    yield StreamTaskMessageStart(
                        type="start",
                        index=message_index,
                        content=TextContent(type="text", author="agent", content=""),
                    )
                    text_streaming = True

                yield StreamTaskMessageDelta(
                    type="delta",
                    index=message_index,
                    delta=TextDelta(type="text", text_delta=chunk.content),
                )

            # ----------------------------------------------------------
            # Case 2: content is a list of typed blocks (reasoning models)
            # Responses API (responses/v1) format:
            #   {"type": "reasoning", "summary": [{"type": "summary_text", "text": "..."}]}
            #   {"type": "text", "text": "..."}
            # ----------------------------------------------------------
            elif isinstance(chunk.content, list):
                for block in chunk.content:
                    if not isinstance(block, dict):
                        continue

                    block_type = block.get("type")

                    if block_type == "reasoning":
                        # Responses API: reasoning text is inside summary list
                        reasoning_text = ""
                        summaries = block.get("summary", [])
                        for s in summaries:
                            if isinstance(s, dict) and s.get("type") == "summary_text":
                                reasoning_text += s.get("text", "")
                        if not reasoning_text:
                            continue

                        # Close text stream if transitioning to reasoning
                        if text_streaming:
                            yield StreamTaskMessageDone(type="done", index=message_index)
                            text_streaming = False
                            message_index += 1

                        if not reasoning_streaming:
                            yield StreamTaskMessageStart(
                                type="start",
                                index=message_index,
                                content=ReasoningContent(
                                    type="reasoning", author="agent", summary=[], content=[], style="active"
                                ),
                            )
                            reasoning_streaming = True
                            reasoning_content_index = 0

                        yield StreamTaskMessageDelta(
                            type="delta",
                            index=message_index,
                            delta=ReasoningContentDelta(
                                type="reasoning_content",
                                content_index=reasoning_content_index,
                                content_delta=reasoning_text,
                            ),
                        )

                    elif block_type == "text":
                        text_delta = block.get("text", "")
                        if not text_delta:
                            continue

                        # Close reasoning stream if transitioning to text
                        if reasoning_streaming:
                            yield StreamTaskMessageDone(type="done", index=message_index)
                            reasoning_streaming = False
                            reasoning_content_index += 1
                            message_index += 1

                        if not text_streaming:
                            yield StreamTaskMessageStart(
                                type="start",
                                index=message_index,
                                content=TextContent(type="text", author="agent", content=""),
                            )
                            text_streaming = True

                        yield StreamTaskMessageDelta(
                            type="delta",
                            index=message_index,
                            delta=TextDelta(type="text", text_delta=text_delta),
                        )

            # ----------------------------------------------------------
            # Reasoning summaries via additional_kwargs (OpenAI v0.3 format)
            # ----------------------------------------------------------
            additional_kwargs = getattr(chunk, "additional_kwargs", {})
            reasoning_kw = additional_kwargs.get("reasoning")
            if isinstance(reasoning_kw, dict):
                summaries = reasoning_kw.get("summary", [])
                for si, summary_item in enumerate(summaries):
                    if isinstance(summary_item, dict) and summary_item.get("type") == "summary_text":
                        summary_text = summary_item.get("text", "")
                        if summary_text:
                            yield StreamTaskMessageDelta(
                                type="delta",
                                index=message_index,
                                delta=ReasoningSummaryDelta(
                                    type="reasoning_summary",
                                    summary_index=si,
                                    summary_delta=summary_text,
                                ),
                            )

        elif event_type == "updates":
            for node_name, state_update in event_data.items():
                if node_name == "agent":
                    messages = state_update.get("messages", [])
                    for msg in messages:
                        # Close any open streams
                        if text_streaming:
                            yield StreamTaskMessageDone(type="done", index=message_index)
                            text_streaming = False
                            message_index += 1
                        if reasoning_streaming:
                            yield StreamTaskMessageDone(type="done", index=message_index)
                            reasoning_streaming = False
                            message_index += 1

                        # Emit tool requests if the agent decided to call tools
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                yield StreamTaskMessageFull(
                                    type="full",
                                    index=message_index,
                                    content=ToolRequestContent(
                                        tool_call_id=tc["id"],
                                        name=tc["name"],
                                        arguments=tc["args"],
                                        author="agent",
                                    ),
                                )
                                message_index += 1

                        # Notify caller of the final AIMessage (e.g. for usage capture)
                        if on_final_ai_message is not None:
                            from langchain_core.messages import AIMessage as _AIMessage

                            if isinstance(msg, _AIMessage):
                                on_final_ai_message(msg)

                elif node_name == "tools":
                    messages = state_update.get("messages", [])
                    for msg in messages:
                        if isinstance(msg, ToolMessage):
                            yield StreamTaskMessageFull(
                                type="full",
                                index=message_index,
                                content=ToolResponseContent(
                                    tool_call_id=msg.tool_call_id,
                                    name=msg.name or "unknown",
                                    content=msg.content if isinstance(msg.content, str) else str(msg.content),
                                    author="agent",
                                ),
                            )
                            message_index += 1

    # Close any remaining open streams
    if text_streaming:
        yield StreamTaskMessageDone(type="done", index=message_index)
    if reasoning_streaming:
        yield StreamTaskMessageDone(type="done", index=message_index)


async def emit_langgraph_messages(messages: list[Any], task_id: str) -> str:
    """Create Agentex messages for a list of LangGraph messages.

    This is the non-streaming counterpart to ``stream_langgraph_events``. Use it
    when you run a LangGraph graph with ``ainvoke`` (for example a Temporal-backed
    agent using the LangGraph plugin, where streaming deltas aren't available) and
    want to surface the resulting messages to the Agentex UI after the fact.

    It maps LangGraph/LangChain message objects to Agentex content types:

    - ``AIMessage`` tool calls   -> ``ToolRequestContent`` (one per call)
    - ``AIMessage`` text content -> ``TextContent``
    - ``ToolMessage``            -> ``ToolResponseContent``

    Pass only the messages produced this turn (e.g. ``messages[already_emitted:]``)
    so each message is surfaced exactly once across a multi-turn conversation.

    Args:
        messages: LangGraph/LangChain message objects to surface — typically
            the new messages a turn produced.
        task_id: The Agentex task to create messages on.

    Returns:
        The last assistant text emitted (useful as a span/turn output), or "".
    """
    # Lazy imports so langchain isn't required at module load time.
    from langchain_core.messages import AIMessage, ToolMessage

    from agentex.lib import adk
    from agentex.types.text_content import TextContent
    from agentex.types.tool_request_content import ToolRequestContent
    from agentex.types.tool_response_content import ToolResponseContent

    final_text = ""
    for message in messages:
        if isinstance(message, AIMessage):
            for tool_call in message.tool_calls or []:
                await adk.messages.create(
                    task_id=task_id,
                    content=ToolRequestContent(
                        author="agent",
                        tool_call_id=tool_call["id"],
                        name=tool_call["name"],
                        arguments=tool_call["args"],
                    ),
                )
            # ``content`` may be a plain string (OpenAI) or a list of content
            # blocks (Anthropic/Claude via LangChain, e.g.
            # ``[{"type": "text", "text": "..."}]``). Extract and join the text
            # so the response is visible regardless of the underlying model.
            if isinstance(message.content, str):
                text = message.content
            else:
                text = "".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in message.content
                    if not isinstance(block, dict) or block.get("type") == "text"
                )
            if text:
                final_text = text
                await adk.messages.create(
                    task_id=task_id,
                    content=TextContent(author="agent", content=text, format="markdown"),
                )
        elif isinstance(message, ToolMessage):
            await adk.messages.create(
                task_id=task_id,
                content=ToolResponseContent(
                    author="agent",
                    tool_call_id=message.tool_call_id,
                    name=message.name or "unknown",
                    content=message.content
                    if isinstance(message.content, str)
                    else str(message.content),
                ),
            )
    return final_text
