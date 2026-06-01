"""Emit finished LangGraph messages as Agentex task messages.

This is the non-streaming counterpart to ``stream_langgraph_events``. Use it
when you run a LangGraph graph with ``ainvoke`` (for example a Temporal-backed
agent using the LangGraph plugin, where streaming deltas aren't available) and
want to surface the resulting messages to the Agentex UI after the fact.

It maps LangGraph/LangChain message objects to Agentex content types:

- ``AIMessage`` tool calls   → ``ToolRequestContent`` (one per call)
- ``AIMessage`` text content → ``TextContent``
- ``ToolMessage``            → ``ToolResponseContent``

Pass only the messages produced this turn (e.g. ``messages[already_emitted:]``)
so each message is surfaced exactly once across a multi-turn conversation.
"""

from __future__ import annotations

from typing import Any


async def emit_langgraph_messages(messages: list[Any], task_id: str) -> str:
    """Create Agentex messages for a list of LangGraph messages.

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
