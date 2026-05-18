"""Async Pydantic AI streaming helper for Agentex.

Consumes a Pydantic AI ``agent.run_stream_events(...)`` async iterator and
pushes Agentex streaming updates to Redis via the ``adk.streaming``
contexts. For use with async ACP agents that stream via Redis rather than
HTTP yields.

Text and thinking tokens stream as deltas inside coalesced streaming
contexts. Tool requests and tool results are emitted as full
``adk.messages.create(...)`` calls (Option A — matches the async LangGraph
helper's convention). To stream tool-call argument tokens, see the sync
converter at ``agentex.lib.adk._modules._pydantic_ai_sync`` which yields
``ToolRequestDelta`` events.
"""


async def stream_pydantic_ai_events(stream, task_id: str) -> str:
    """Stream Pydantic AI events to Agentex via Redis.

    Args:
        stream: Async iterator yielded by ``agent.run_stream_events(...)``.
        task_id: The Agentex task ID to stream messages to.

    Returns:
        The accumulated text content of the **last** text part in the run.
        Multi-step runs (where the model emits text, then a tool call, then
        more text) return only the final text segment, matching the
        ``stream_langgraph_events`` convention.
    """
    # Lazy imports so pydantic-ai isn't required at module load time.
    import json

    from pydantic_ai.messages import (
        FunctionToolResultEvent,
        PartDeltaEvent,
        PartEndEvent,
        PartStartEvent,
        TextPart,
        TextPartDelta,
        ThinkingPart,
        ThinkingPartDelta,
        ToolCallPart,
    )

    from agentex.lib import adk
    from agentex.types.text_content import TextContent
    from agentex.types.reasoning_content import ReasoningContent
    from agentex.types.task_message_delta import TextDelta
    from agentex.types.task_message_update import StreamTaskMessageDelta
    from agentex.types.tool_request_content import ToolRequestContent
    from agentex.types.tool_response_content import ToolResponseContent
    from agentex.types.reasoning_content_delta import ReasoningContentDelta

    text_context = None
    reasoning_context = None
    final_text = ""

    # Per Pydantic-AI part-index bookkeeping. Part indices restart at 0 on
    # each new model response, so we overwrite on PartStartEvent.
    part_kind: dict[int, str] = {}
    tool_call_info: dict[int, tuple[str, str]] = {}

    async def _close_text():
        nonlocal text_context
        if text_context:
            await text_context.close()
            text_context = None

    async def _close_reasoning():
        nonlocal reasoning_context
        if reasoning_context:
            await reasoning_context.close()
            reasoning_context = None

    try:
        async for event in stream:
            if isinstance(event, PartStartEvent):
                if isinstance(event.part, TextPart):
                    await _close_reasoning()
                    await _close_text()

                    final_text = ""
                    text_context = await adk.streaming.streaming_task_message_context(
                        task_id=task_id,
                        initial_content=TextContent(
                            author="agent",
                            content="",
                            format="markdown",
                        ),
                    ).__aenter__()
                    part_kind[event.index] = "text"

                    # Pydantic AI puts the first streaming chunk in
                    # PartStartEvent.part.content; surface it as a Delta so it
                    # actually renders (Start.content is initialization, not body).
                    if event.part.content:
                        final_text += event.part.content
                        await text_context.stream_update(
                            StreamTaskMessageDelta(
                                parent_task_message=text_context.task_message,
                                delta=TextDelta(type="text", text_delta=event.part.content),
                                type="delta",
                            )
                        )

                elif isinstance(event.part, ThinkingPart):
                    await _close_text()
                    await _close_reasoning()

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
                    part_kind[event.index] = "reasoning"

                    if event.part.content:
                        await reasoning_context.stream_update(
                            StreamTaskMessageDelta(
                                parent_task_message=reasoning_context.task_message,
                                delta=ReasoningContentDelta(
                                    type="reasoning_content",
                                    content_index=0,
                                    content_delta=event.part.content,
                                ),
                                type="delta",
                            )
                        )

                elif isinstance(event.part, ToolCallPart):
                    await _close_text()
                    await _close_reasoning()
                    tool_call_info[event.index] = (
                        event.part.tool_call_id,
                        event.part.tool_name,
                    )
                    part_kind[event.index] = "tool_call"

            elif isinstance(event, PartDeltaEvent):
                kind = part_kind.get(event.index)
                if kind == "text" and isinstance(event.delta, TextPartDelta) and text_context:
                    final_text += event.delta.content_delta
                    await text_context.stream_update(
                        StreamTaskMessageDelta(
                            parent_task_message=text_context.task_message,
                            delta=TextDelta(type="text", text_delta=event.delta.content_delta),
                            type="delta",
                        )
                    )
                elif (
                    kind == "reasoning"
                    and isinstance(event.delta, ThinkingPartDelta)
                    and reasoning_context
                    and event.delta.content_delta
                ):
                    await reasoning_context.stream_update(
                        StreamTaskMessageDelta(
                            parent_task_message=reasoning_context.task_message,
                            delta=ReasoningContentDelta(
                                type="reasoning_content",
                                content_index=0,
                                content_delta=event.delta.content_delta,
                            ),
                            type="delta",
                        )
                    )
                # Tool-call arg deltas: Pydantic AI accumulates them; we
                # surface the final args on PartEndEvent below (Option A).

            elif isinstance(event, PartEndEvent):
                kind = part_kind.get(event.index)
                if kind == "text":
                    await _close_text()
                elif kind == "reasoning":
                    await _close_reasoning()
                elif kind == "tool_call" and isinstance(event.part, ToolCallPart):
                    tool_call_id, tool_name = tool_call_info.get(event.index, ("", ""))
                    args = event.part.args
                    if isinstance(args, str):
                        try:
                            args = json.loads(args) if args else {}
                        except json.JSONDecodeError:
                            args = {"_raw": args}
                    elif args is None:
                        args = {}
                    await adk.messages.create(
                        task_id=task_id,
                        content=ToolRequestContent(
                            tool_call_id=tool_call_id,
                            name=tool_name,
                            arguments=args,
                            author="agent",
                        ),
                    )

            elif isinstance(event, FunctionToolResultEvent):
                await _close_text()
                await _close_reasoning()

                result = event.part
                tool_call_id = result.tool_call_id
                tool_name = getattr(result, "tool_name", "") or ""
                content = getattr(result, "content", None)
                if content is None:
                    content_str = str(result)
                elif isinstance(content, str):
                    content_str = content
                else:
                    content_str = str(content)
                await adk.messages.create(
                    task_id=task_id,
                    content=ToolResponseContent(
                        tool_call_id=tool_call_id,
                        name=tool_name,
                        content=content_str,
                        author="agent",
                    ),
                )

            # FunctionToolCallEvent / FinalResultEvent / AgentRunResultEvent
            # are intentionally ignored — same as the sync converter.

    finally:
        if text_context:
            await text_context.close()
        if reasoning_context:
            await reasoning_context.close()

    return final_text
