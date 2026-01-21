"""Async LangGraph streaming helper for Agentex.

Converts LangGraph graph.astream() events into Agentex streaming updates
and pushes them to Redis via adk.streaming contexts. For use with async
ACP agents that stream via Redis rather than HTTP yields.
"""


async def stream_langgraph_events(stream, task_id: str) -> str:
    """Stream LangGraph events to Agentex via Redis.

    Processes the stream from graph.astream() called with
    stream_mode=["messages", "updates"] and pushes text, reasoning,
    tool request, and tool response messages through Redis streaming
    contexts.

    Supports both regular models (chunk.content is a str) and reasoning
    models like gpt-5/o1/o3 (chunk.content is a list of typed content blocks
    in the Responses API responses/v1 format).

    Args:
        stream: Async iterator from graph.astream(..., stream_mode=["messages", "updates"])
        task_id: The Agentex task ID to stream messages to.

    Returns:
        The accumulated final text output from the agent.
    """
    # Lazy imports so langgraph/langchain aren't required at module load time
    from langchain_core.messages import ToolMessage, AIMessageChunk

    from agentex.lib import adk
    from agentex.types.text_content import TextContent
    from agentex.types.reasoning_content import ReasoningContent
    from agentex.types.task_message_delta import TextDelta
    from agentex.types.task_message_update import StreamTaskMessageDelta
    from agentex.types.tool_request_content import ToolRequestContent
    from agentex.types.tool_response_content import ToolResponseContent
    from agentex.types.reasoning_summary_delta import ReasoningSummaryDelta

    text_context = None
    reasoning_context = None
    final_text = ""

    try:
        async for event_type, event_data in stream:
            if event_type == "messages":
                chunk, metadata = event_data

                if not isinstance(chunk, AIMessageChunk) or not chunk.content:
                    continue

                # ----------------------------------------------------------
                # Case 1: content is a plain string (regular models)
                # ----------------------------------------------------------
                if isinstance(chunk.content, str):
                    if reasoning_context:
                        await reasoning_context.close()
                        reasoning_context = None

                    if not text_context:
                        final_text = ""
                        text_context = await adk.streaming.streaming_task_message_context(
                            task_id=task_id,
                            initial_content=TextContent(
                                author="agent",
                                content="",
                                format="markdown",
                            ),
                        ).__aenter__()

                    final_text += chunk.content
                    await text_context.stream_update(
                        StreamTaskMessageDelta(
                            parent_task_message=text_context.task_message,
                            delta=TextDelta(type="text", text_delta=chunk.content),
                            type="delta",
                        )
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
                            reasoning_text = ""
                            for s in block.get("summary", []):
                                if isinstance(s, dict) and s.get("type") == "summary_text":
                                    reasoning_text += s.get("text", "")
                            if not reasoning_text:
                                continue

                            if text_context:
                                await text_context.close()
                                text_context = None

                            if not reasoning_context:
                                reasoning_context = await adk.streaming.streaming_task_message_context(
                                    task_id=task_id,
                                    initial_content=ReasoningContent(
                                        author="agent",
                                        summary=[],
                                        content=[],
                                        type="reasoning",
                                        style="active",
                                    ),
                                ).__aenter__()

                            await reasoning_context.stream_update(
                                StreamTaskMessageDelta(
                                    parent_task_message=reasoning_context.task_message,
                                    delta=ReasoningSummaryDelta(
                                        type="reasoning_summary",
                                        summary_index=0,
                                        summary_delta=reasoning_text,
                                    ),
                                    type="delta",
                                )
                            )

                        elif block_type == "text":
                            text_delta = block.get("text", "")
                            if not text_delta:
                                continue

                            if reasoning_context:
                                await reasoning_context.close()
                                reasoning_context = None

                            if not text_context:
                                final_text = ""
                                text_context = await adk.streaming.streaming_task_message_context(
                                    task_id=task_id,
                                    initial_content=TextContent(
                                        author="agent",
                                        content="",
                                        format="markdown",
                                    ),
                                ).__aenter__()

                            final_text += text_delta
                            await text_context.stream_update(
                                StreamTaskMessageDelta(
                                    parent_task_message=text_context.task_message,
                                    delta=TextDelta(type="text", text_delta=text_delta),
                                    type="delta",
                                )
                            )

            elif event_type == "updates":
                for node_name, state_update in event_data.items():
                    if node_name == "agent":
                        messages = state_update.get("messages", [])
                        for msg in messages:
                            if text_context:
                                await text_context.close()
                                text_context = None
                            if reasoning_context:
                                await reasoning_context.close()
                                reasoning_context = None

                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    await adk.messages.create(
                                        task_id=task_id,
                                        content=ToolRequestContent(
                                            tool_call_id=tc["id"],
                                            name=tc["name"],
                                            arguments=tc["args"],
                                            author="agent",
                                        ),
                                    )

                    elif node_name == "tools":
                        messages = state_update.get("messages", [])
                        for msg in messages:
                            if isinstance(msg, ToolMessage):
                                await adk.messages.create(
                                    task_id=task_id,
                                    content=ToolResponseContent(
                                        tool_call_id=msg.tool_call_id,
                                        name=msg.name or "unknown",
                                        content=msg.content if isinstance(msg.content, str) else str(msg.content),
                                        author="agent",
                                    ),
                                )
    finally:
        # Always close open contexts
        if text_context:
            await text_context.close()
        if reasoning_context:
            await reasoning_context.close()

    return final_text
