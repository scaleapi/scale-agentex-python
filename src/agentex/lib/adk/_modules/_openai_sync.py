"""Sync OpenAI Agents SDK streaming tap for Agentex.

Converts an OpenAI Agents SDK streamed run (``Runner.run_streamed(...)``
``stream_events()``) into Agentex ``StreamTaskMessage*`` events, including
reasoning content and reasoning summary deltas for reasoning models (o1/o3/gpt-5).

This is the lower-level primitive used by ``OpenAITurn`` (in
``_openai_turn.py``). New OpenAI Agents integrations should prefer wrapping a
``Runner.run_streamed`` result in ``OpenAITurn`` and driving delivery + tracing
through ``UnifiedEmitter``.
"""

from __future__ import annotations

import json
from typing import Any

from openai.types.responses import (
    ResponseTextDeltaEvent,
    ResponseFunctionToolCall,
    ResponseFunctionWebSearch,
    ResponseOutputItemDoneEvent,
    ResponseOutputItemAddedEvent,
    ResponseCodeInterpreterToolCall,
    ResponseReasoningSummaryPartAddedEvent,
    ResponseReasoningSummaryTextDeltaEvent,
)
from openai.types.responses.response_reasoning_text_done_event import ResponseReasoningTextDoneEvent
from openai.types.responses.response_reasoning_text_delta_event import ResponseReasoningTextDeltaEvent
from openai.types.responses.response_reasoning_summary_text_done_event import ResponseReasoningSummaryTextDoneEvent

from agentex.types.reasoning_content import ReasoningContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.task_message_content import TextContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.types.reasoning_content_delta import ReasoningContentDelta
from agentex.types.reasoning_summary_delta import ReasoningSummaryDelta


def _safe_parse_arguments(arguments: Any) -> dict[str, Any]:
    """Coerce a tool call's ``arguments`` into a dict, tolerating bad JSON.

    ``ToolRequestContent.arguments`` is typed ``Dict[str, object]``, so the
    result is ALWAYS a dict — a non-dict payload must not abort the turn.
    Mirroring the Temporal streaming model: malformed/truncated strings are
    preserved under ``raw``, and any other non-dict value (a list, scalar, or
    SDK object) is serialized if possible, otherwise wrapped under ``value``.
    """
    if not arguments:
        return {}
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except (json.JSONDecodeError, ValueError):
            return {"raw": arguments}
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    # Non-string, non-dict (e.g. a provider tool passing a list / scalar / SDK
    # object). Prefer the object's own dict form; fall back to wrapping it.
    dumped = arguments.model_dump() if hasattr(arguments, "model_dump") else None
    if isinstance(dumped, dict):
        return dumped
    return {"value": arguments}


def _extract_tool_call_info(tool_call_item: Any) -> tuple[str, str, dict[str, Any]]:
    """
    Extract call_id, tool_name, and tool_arguments from a tool call item.
    Args:
        tool_call_item: The tool call item to process
    Returns:
        A tuple of (call_id, tool_name, tool_arguments)
    """
    # Generic handling for different tool call types
    # Try 'call_id' first, then 'id', then generate placeholder
    if hasattr(tool_call_item, "call_id"):
        call_id = tool_call_item.call_id
    elif hasattr(tool_call_item, "id"):
        call_id = tool_call_item.id
    else:
        call_id = f"unknown_call_{id(tool_call_item)}"

    if isinstance(tool_call_item, ResponseFunctionWebSearch):
        tool_name = "web_search"
        tool_arguments = {"action": tool_call_item.action.model_dump(), "status": tool_call_item.status}
    elif isinstance(tool_call_item, ResponseCodeInterpreterToolCall):
        tool_name = "code_interpreter"
        tool_arguments = {"code": tool_call_item.code, "status": tool_call_item.status}
    elif isinstance(tool_call_item, ResponseFunctionToolCall):
        # Handle standard function tool calls
        tool_name = tool_call_item.name
        tool_arguments = _safe_parse_arguments(tool_call_item.arguments)
    else:
        # Generic handling for any tool call type
        tool_name = getattr(tool_call_item, "name", type(tool_call_item).__name__)
        if hasattr(tool_call_item, "arguments"):
            tool_arguments = _safe_parse_arguments(tool_call_item.arguments)
        else:
            tool_arguments = tool_call_item.model_dump()

    return call_id, tool_name, tool_arguments


def _extract_tool_response_info(tool_map: dict[str, Any], tool_output_item: Any) -> tuple[str, str, str]:
    """
    Extract call_id, tool_name, and content from a tool output item.
    Args:
        tool_map: Dictionary mapping call_ids to tool names
        tool_output_item: The tool output item to process
    Returns:
        A tuple of (call_id, tool_name, content)
    """

    # Handle different formats of tool_output_item
    if isinstance(tool_output_item, dict):
        call_id = tool_output_item.get("call_id", tool_output_item.get("id", f"unknown_call_{id(tool_output_item)}"))
        content = tool_output_item.get("output", str(tool_output_item))
    else:
        # Try to get call_id from attributes
        if hasattr(tool_output_item, "call_id"):
            call_id = tool_output_item.call_id
        elif hasattr(tool_output_item, "id"):
            call_id = tool_output_item.id
        else:
            call_id = f"unknown_call_{id(tool_output_item)}"

        # Get content
        if hasattr(tool_output_item, "output"):
            content = tool_output_item.output
        else:
            content = str(tool_output_item)

    # Get tool name from map
    tool_name = tool_map.get(call_id, "unknown_tool")

    return call_id, tool_name, content


async def convert_openai_to_agentex_events(stream_response):
    """Convert OpenAI streaming events to AgentEx TaskMessageUpdate events with reasoning support.

    This is an enhanced version of the base converter that includes support for:
    - Reasoning content deltas (for o1 models)
    - Reasoning summary deltas (for o1 models)

    Args:
        stream_response: An async iterator of OpenAI streaming events
    Yields:
        TaskMessageUpdate: AgentEx streaming events (StreamTaskMessageDelta, StreamTaskMessageFull, or StreamTaskMessageDone)
    """

    tool_map = {}
    event_count = 0
    message_index = 0  # Track message index for proper sequencing
    item_id_to_index = {}  # Map item_id to message index
    item_id_to_type = {}  # Map item_id to content type (text, reasoning_content, reasoning_summary)

    async for event in stream_response:
        event_count += 1

        # Check for raw response events which contain the actual OpenAI streaming events
        if hasattr(event, "type") and event.type == "raw_response_event":
            if hasattr(event, "data"):
                raw_event = event.data

                # Check for ResponseOutputItemAddedEvent which signals a new message starting
                if isinstance(raw_event, ResponseOutputItemAddedEvent):
                    # Don't increment here - we'll increment when we see the actual text delta
                    # This is just a signal that a new message is starting
                    pass

                # Handle item completion - send done event to close the message
                elif isinstance(raw_event, ResponseOutputItemDoneEvent):
                    item_id = raw_event.item.id
                    if item_id in item_id_to_index:
                        # Close every streamed message — text AND reasoning — with a
                        # matching Done. UnifiedEmitter.auto_send only releases a
                        # context on StreamTaskMessageDone; skipping it for reasoning
                        # left those messages hanging and their spans incomplete. The
                        # accumulator rebuilds ReasoningContent from the deltas, so the
                        # Done carries no payload.
                        yield StreamTaskMessageDone(
                            type="done",
                            index=item_id_to_index[item_id],
                        )

                # Skip reasoning summary part added events - we handle them on delta
                elif isinstance(raw_event, ResponseReasoningSummaryPartAddedEvent):
                    pass

                # Handle reasoning summary text delta events
                elif isinstance(raw_event, ResponseReasoningSummaryTextDeltaEvent):
                    item_id = raw_event.item_id
                    summary_index = raw_event.summary_index

                    # If this is a new item_id we haven't seen, create a new message
                    if item_id and item_id not in item_id_to_index:
                        message_index += 1
                        item_id_to_index[item_id] = message_index
                        item_id_to_type[item_id] = "reasoning_summary"

                        # Send a start event for this new reasoning summary message.
                        # The start content must be ReasoningContent (not TextContent)
                        # so consumers that branch on the start event's content type
                        # render a reasoning/thinking indicator; the final persisted
                        # content is rebuilt from the reasoning deltas regardless.
                        yield StreamTaskMessageStart(
                            type="start",
                            index=item_id_to_index[item_id],
                            content=ReasoningContent(
                                type="reasoning",
                                author="agent",
                                summary=[],
                                content=[],
                                style="active",
                            ),
                        )

                    # Use the index for this item_id
                    current_index = item_id_to_index.get(item_id, message_index)

                    # Yield reasoning summary delta
                    yield StreamTaskMessageDelta(
                        type="delta",
                        index=current_index,
                        delta=ReasoningSummaryDelta(
                            type="reasoning_summary",
                            summary_index=summary_index,
                            summary_delta=raw_event.delta,
                        ),
                    )

                # Handle reasoning summary text done events
                elif isinstance(raw_event, ResponseReasoningSummaryTextDoneEvent):
                    # We do NOT close the streaming context here
                    # as there can be multiple reasoning summaries.
                    # The context will be closed when the entire
                    # output item is done (ResponseOutputItemDoneEvent)
                    pass

                # Handle reasoning content text delta events
                elif isinstance(raw_event, ResponseReasoningTextDeltaEvent):
                    item_id = raw_event.item_id
                    content_index = raw_event.content_index

                    # If this is a new item_id we haven't seen, create a new message
                    if item_id and item_id not in item_id_to_index:
                        message_index += 1
                        item_id_to_index[item_id] = message_index
                        item_id_to_type[item_id] = "reasoning_content"

                        # Send a start event for this new reasoning content message.
                        # The start content must be ReasoningContent (not TextContent)
                        # so consumers that branch on the start event's content type
                        # render a reasoning/thinking indicator; the final persisted
                        # content is rebuilt from the reasoning deltas regardless.
                        yield StreamTaskMessageStart(
                            type="start",
                            index=item_id_to_index[item_id],
                            content=ReasoningContent(
                                type="reasoning",
                                author="agent",
                                summary=[],
                                content=[],
                                style="active",
                            ),
                        )

                    # Use the index for this item_id
                    current_index = item_id_to_index.get(item_id, message_index)

                    # Yield reasoning content delta
                    yield StreamTaskMessageDelta(
                        type="delta",
                        index=current_index,
                        delta=ReasoningContentDelta(
                            type="reasoning_content",
                            content_index=content_index,
                            content_delta=raw_event.delta,
                        ),
                    )

                # Handle reasoning content text done events
                elif isinstance(raw_event, ResponseReasoningTextDoneEvent):
                    # We do NOT close the streaming context here
                    # as there can be multiple reasoning content texts.
                    # The context will be closed when the entire
                    # output item is done (ResponseOutputItemDoneEvent)
                    pass

                # Check if this is a text delta event from OpenAI
                elif isinstance(raw_event, ResponseTextDeltaEvent):
                    # Check if this event has an item_id
                    item_id = getattr(raw_event, "item_id", None)

                    # If this is a new item_id we haven't seen, it's a new message.
                    # Reserve a fresh index for every text item_id (matching the
                    # increment-then-use convention of the reasoning/tool paths).
                    # Reusing the current index let a final answer collide with the
                    # preceding reasoning message on reasoning-model streams.
                    if item_id and item_id not in item_id_to_index:
                        message_index += 1
                        item_id_to_index[item_id] = message_index
                        item_id_to_type[item_id] = "text"

                        # Send a start event with empty content for this new text message
                        yield StreamTaskMessageStart(
                            type="start",
                            index=item_id_to_index[item_id],
                            content=TextContent(
                                type="text",
                                author="agent",
                                content="",  # Start with empty content, deltas will fill it
                            ),
                        )

                    # Use the index for this item_id
                    current_index = item_id_to_index.get(item_id, message_index)

                    delta_message = StreamTaskMessageDelta(
                        type="delta",
                        index=current_index,
                        delta=TextDelta(
                            type="text",
                            text_delta=raw_event.delta,
                        ),
                    )
                    yield delta_message

        elif hasattr(event, "type") and event.type == "run_item_stream_event":
            # Skip reasoning_item events - they're handled via raw_response_event above
            if hasattr(event, "item") and event.item.type == "reasoning_item":
                continue

            # Check for tool_call_item type (this is when a tool is being called)
            elif hasattr(event, "item") and event.item.type == "tool_call_item":
                # Extract tool call information using the helper method
                call_id, tool_name, tool_arguments = _extract_tool_call_info(event.item.raw_item)
                tool_map[call_id] = tool_name
                tool_request_content = ToolRequestContent(
                    tool_call_id=call_id,
                    name=tool_name,
                    arguments=tool_arguments,
                    author="agent",
                )
                message_index += 1  # Increment for new message
                yield StreamTaskMessageFull(
                    index=message_index,
                    type="full",
                    content=tool_request_content,
                )

            # Check for tool_call_output_item type (this is when a tool returns output)
            elif hasattr(event, "item") and event.item.type == "tool_call_output_item":
                # Extract tool response information using the helper method
                call_id, tool_name, content = _extract_tool_response_info(tool_map, event.item.raw_item)
                tool_response_content = ToolResponseContent(
                    tool_call_id=call_id,
                    name=tool_name,
                    content=content,
                    author="agent",
                )
                message_index += 1  # Increment for new message
                yield StreamTaskMessageFull(
                    type="full",
                    index=message_index,
                    content=tool_response_content,
                )
