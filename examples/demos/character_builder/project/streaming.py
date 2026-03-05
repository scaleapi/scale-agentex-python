"""Convert OpenAI Agent SDK stream events to AgentEx streaming events.

The SDK's built-in converter doesn't handle multi-agent handoffs correctly —
handoff tool calls don't emit a tool_call_output_item, so the message index
never increments and the next agent's text overwrites the tool call in the UI.

This converter always assigns a fresh index to each new text or tool-call item.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from agentex.types.task_message_content import TextContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDelta,
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agents.stream_events import RawResponsesStreamEvent, RunItemStreamEvent
from openai.types.responses import ResponseOutputItemDoneEvent, ResponseTextDeltaEvent

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from agentex.types.task_message_update import TaskMessageUpdate


async def stream_agent_events(stream_response) -> AsyncGenerator[TaskMessageUpdate, None]:  # noqa: ANN001, C901
    """Yield AgentEx streaming events from an OpenAI Agent SDK run stream."""
    message_index = 0
    item_id_to_index: dict[str, int] = {}
    tool_call_ids: dict[str, str] = {}

    async for event in stream_response:
        if isinstance(event, RawResponsesStreamEvent):
            raw = event.data

            if isinstance(raw, ResponseTextDeltaEvent):
                item_id = raw.item_id

                if item_id not in item_id_to_index:
                    message_index += 1
                    item_id_to_index[item_id] = message_index
                    yield StreamTaskMessageStart(
                        type="start",
                        index=message_index,
                        content=TextContent(type="text", author="agent", content=""),
                    )

                yield StreamTaskMessageDelta(
                    type="delta",
                    index=item_id_to_index[item_id],
                    delta=TextDelta(type="text", text_delta=raw.delta),
                )

            elif isinstance(raw, ResponseOutputItemDoneEvent):
                item_id = raw.item.id
                if item_id in item_id_to_index:
                    yield StreamTaskMessageDone(type="done", index=item_id_to_index[item_id])

        elif isinstance(event, RunItemStreamEvent):
            raw_item = event.item.raw_item

            if event.item.type == "tool_call_item":
                # raw_item is a ResponseFunctionToolCall object
                call_id = raw_item.call_id
                name = raw_item.name
                args_str = raw_item.arguments
                tool_call_ids[call_id] = name

                message_index += 1
                yield StreamTaskMessageFull(
                    type="full",
                    index=message_index,
                    content=ToolRequestContent(
                        tool_call_id=call_id,
                        name=name,
                        arguments=json.loads(args_str) if args_str else {},
                        author="agent",
                    ),
                )

            elif event.item.type == "tool_call_output_item":
                # raw_item is a dict
                call_id = raw_item["call_id"]
                output = raw_item["output"]

                message_index += 1
                yield StreamTaskMessageFull(
                    type="full",
                    index=message_index,
                    content=ToolResponseContent(
                        tool_call_id=call_id,
                        name=tool_call_ids.get(call_id, "unknown"),
                        content=output,
                        author="agent",
                    ),
                )
