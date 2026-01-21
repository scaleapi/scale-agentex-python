"""Sync LangGraph streaming helper for Agentex.

Converts LangGraph graph.astream() events into Agentex TaskMessageUpdate
events that are yielded back over the HTTP response. For use with sync ACP
agents that stream via HTTP yields rather than Redis.
"""


async def convert_langgraph_to_agentex_events(stream):
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

    Args:
        stream: Async iterator from graph.astream(..., stream_mode=["messages", "updates"])

    Yields:
        TaskMessageUpdate events (Start, Delta, Done, Full)
    """
    # Lazy imports so langgraph/langchain aren't required at module load time
    from langchain_core.messages import ToolMessage, AIMessageChunk

    from agentex.types.text_content import TextContent
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
                                content=TextContent(type="text", author="agent", content=""),
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
