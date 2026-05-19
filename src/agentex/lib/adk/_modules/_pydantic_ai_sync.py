"""Pydantic AI streaming integration for Agentex.

Converts a Pydantic AI ``AgentStreamEvent`` stream (as yielded by
``agent.run_stream_events(...)`` or via an ``event_stream_handler``) into the
Agentex ``StreamTaskMessage*`` events that the Agentex server understands.

Typical sync usage:

    from pydantic_ai import Agent
    from agentex.lib.adk import convert_pydantic_ai_to_agentex_events

    agent = Agent("openai:gpt-4o", system_prompt="...")

    @acp.on_message_send
    async def handle_message_send(params):
        async with agent.run_stream_events(params.content.content) as stream:
            async for event in convert_pydantic_ai_to_agentex_events(stream):
                yield event
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, AsyncIterator

from pydantic_ai.run import AgentRunResultEvent

if TYPE_CHECKING:
    from agentex.lib.adk._modules._pydantic_ai_tracing import (
        AgentexPydanticAITracingHandler,
    )
from pydantic_ai.messages import (
    TextPart,
    PartEndEvent,
    ThinkingPart,
    ToolCallPart,
    TextPartDelta,
    PartDeltaEvent,
    PartStartEvent,
    ToolReturnPart,
    FinalResultEvent,
    ThinkingPartDelta,
    ToolCallPartDelta,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
)

from agentex.lib.utils.logging import make_logger
from agentex.types.task_message_delta import TextDelta
from agentex.types.tool_request_delta import ToolRequestDelta
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

logger = make_logger(__name__)


def _args_delta_to_str(args_delta: str | dict[str, Any] | None) -> str:
    """Normalize a Pydantic AI ``ToolCallPartDelta.args_delta`` to a string fragment.

    Pydantic AI emits string fragments for providers that stream JSON tokens
    (OpenAI, Anthropic) and dicts for providers that emit one-shot tool calls.
    Agentex's ``ToolRequestDelta.arguments_delta`` is concatenated server-side
    and parsed as a single JSON object on completion, so we always produce a
    string. For dict deltas this is a one-shot dump; subsequent dict deltas
    will not compose correctly, but in practice dict deltas arrive as a single
    final fragment.
    """
    if args_delta is None:
        return ""
    if isinstance(args_delta, str):
        return args_delta
    return json.dumps(args_delta)


def _tool_return_content(result: ToolReturnPart | Any) -> Any:
    """Best-effort extraction of the user-visible content from a tool result.

    ``FunctionToolResultEvent.part`` is ``ToolReturnPart | RetryPromptPart``.
    For ``ToolReturnPart`` we surface ``.content`` directly; for ``RetryPromptPart``
    (a retry signal back to the model) we surface a string description so the
    UI sees the failure reason.
    """
    content = getattr(result, "content", None)
    if content is None:
        return str(result)
    if isinstance(content, (str, int, float, bool, list, dict)):
        return content
    if hasattr(content, "model_dump"):
        try:
            return content.model_dump()
        except Exception:
            return str(content)
    return str(content)


async def convert_pydantic_ai_to_agentex_events(
    stream_response: AsyncIterator[Any],
    tracing_handler: "AgentexPydanticAITracingHandler | None" = None,
) -> AsyncIterator[StreamTaskMessageStart | StreamTaskMessageDelta | StreamTaskMessageFull | StreamTaskMessageDone]:
    """Convert a Pydantic AI agent event stream into Agentex stream events.

    Mapping:
        PartStartEvent(TextPart)       -> StreamTaskMessageStart(TextContent)
        PartStartEvent(ThinkingPart)   -> StreamTaskMessageStart(TextContent)         [reasoning channel]
        PartStartEvent(ToolCallPart)   -> StreamTaskMessageStart(ToolRequestContent)
        PartDeltaEvent(TextPartDelta)  -> StreamTaskMessageDelta(TextDelta)
        PartDeltaEvent(ThinkingPart..) -> StreamTaskMessageDelta(ReasoningContentDelta)
        PartDeltaEvent(ToolCallPart..) -> StreamTaskMessageDelta(ToolRequestDelta)
        PartEndEvent                   -> StreamTaskMessageDone
        FunctionToolResultEvent        -> StreamTaskMessageFull(ToolResponseContent)
        FunctionToolCallEvent          -> (ignored — already covered by Start/Delta/End)
        FinalResultEvent               -> (ignored — informational; the run-level
                                          AgentRunResultEvent terminates the stream)
        AgentRunResultEvent            -> (ignored — Agentex closes the per-message
                                          stream via PartEndEvent already)

    Args:
        stream_response: The async iterator yielded by Pydantic AI's
            ``agent.run_stream_events(...)`` context manager (or a stream of
            ``AgentStreamEvent`` items received in an ``event_stream_handler``).
        tracing_handler: Optional handler from
            ``create_pydantic_ai_tracing_handler(...)``. When provided, each
            tool call in the run is also recorded as an Agentex child span
            beneath the handler's configured ``parent_span_id``. Streaming
            behavior is unchanged when omitted.

    Yields:
        Agentex ``StreamTaskMessage*`` events suitable for forwarding back over
        the ACP streaming response.
    """
    next_message_index = 0
    # Maps Pydantic AI's per-response part index to our absolute message index.
    # Part indices restart at 0 on each new model response in a multi-step run,
    # so we always overwrite the entry on PartStartEvent.
    part_to_message_index: dict[int, int] = {}
    # Tool-call metadata indexed by Pydantic AI part index (so deltas can
    # surface the tool_call_id even when ToolCallPartDelta.tool_call_id is None).
    tool_call_meta: dict[int, tuple[str, str]] = {}

    async for event in stream_response:
        if isinstance(event, PartStartEvent):
            message_index = next_message_index
            next_message_index += 1
            part_to_message_index[event.index] = message_index

            if isinstance(event.part, TextPart):
                yield StreamTaskMessageStart(
                    type="start",
                    index=message_index,
                    content=TextContent(
                        type="text",
                        author="agent",
                        content="",
                    ),
                )
                if event.part.content:
                    yield StreamTaskMessageDelta(
                        type="delta",
                        index=message_index,
                        delta=TextDelta(type="text", text_delta=event.part.content),
                    )
            elif isinstance(event.part, ThinkingPart):
                yield StreamTaskMessageStart(
                    type="start",
                    index=message_index,
                    content=TextContent(
                        type="text",
                        author="agent",
                        content="",
                    ),
                )
                if event.part.content:
                    yield StreamTaskMessageDelta(
                        type="delta",
                        index=message_index,
                        delta=ReasoningContentDelta(
                            type="reasoning_content",
                            content_index=0,
                            content_delta=event.part.content,
                        ),
                    )
            elif isinstance(event.part, ToolCallPart):
                tool_call_meta[event.index] = (event.part.tool_call_id, event.part.tool_name)
                # Pydantic AI may already have a fully-formed args dict at start
                # when the provider returns the tool call in one shot; surface it
                # directly so clients see the complete arguments without waiting
                # for deltas.
                initial_args: dict[str, Any] = {}
                if isinstance(event.part.args, dict):
                    # dict(...) materializes a fresh dict[str, Any]; pydantic-ai's
                    # ToolCallPart.args includes TypedDict-style variants that
                    # pyright doesn't narrow to plain dict[str, Any] via isinstance.
                    initial_args = dict(event.part.args)
                yield StreamTaskMessageStart(
                    type="start",
                    index=message_index,
                    content=ToolRequestContent(
                        type="tool_request",
                        author="agent",
                        tool_call_id=event.part.tool_call_id,
                        name=event.part.tool_name,
                        arguments=initial_args,
                    ),
                )
                if isinstance(event.part.args, str) and event.part.args:
                    yield StreamTaskMessageDelta(
                        type="delta",
                        index=message_index,
                        delta=ToolRequestDelta(
                            type="tool_request",
                            tool_call_id=event.part.tool_call_id,
                            name=event.part.tool_name,
                            arguments_delta=event.part.args,
                        ),
                    )
            else:
                logger.debug("Unhandled PartStartEvent part type: %r", type(event.part).__name__)

        elif isinstance(event, PartDeltaEvent):
            message_index = part_to_message_index.get(event.index)
            if message_index is None:
                logger.debug("PartDeltaEvent for unknown part index %s; skipping", event.index)
                continue

            if isinstance(event.delta, TextPartDelta):
                yield StreamTaskMessageDelta(
                    type="delta",
                    index=message_index,
                    delta=TextDelta(type="text", text_delta=event.delta.content_delta),
                )
            elif isinstance(event.delta, ThinkingPartDelta):
                if event.delta.content_delta:
                    yield StreamTaskMessageDelta(
                        type="delta",
                        index=message_index,
                        delta=ReasoningContentDelta(
                            type="reasoning_content",
                            content_index=0,
                            content_delta=event.delta.content_delta,
                        ),
                    )
            elif isinstance(event.delta, ToolCallPartDelta):
                meta = tool_call_meta.get(event.index)
                if meta is None:
                    # First time we've seen this part; the provider didn't emit
                    # a PartStartEvent first. Synthesize one from the delta if
                    # we have enough information.
                    tool_call_id = event.delta.tool_call_id or ""
                    tool_name = event.delta.tool_name_delta or ""
                    tool_call_meta[event.index] = (tool_call_id, tool_name)
                else:
                    tool_call_id, tool_name = meta
                yield StreamTaskMessageDelta(
                    type="delta",
                    index=message_index,
                    delta=ToolRequestDelta(
                        type="tool_request",
                        tool_call_id=tool_call_id,
                        name=tool_name,
                        arguments_delta=_args_delta_to_str(event.delta.args_delta),
                    ),
                )
            else:
                logger.debug("Unhandled PartDeltaEvent delta type: %r", type(event.delta).__name__)

        elif isinstance(event, PartEndEvent):
            message_index = part_to_message_index.get(event.index)
            if message_index is None:
                continue
            yield StreamTaskMessageDone(type="done", index=message_index)
            # Tool-call parts end with the model's full args known. Open a
            # tracing child span for the tool execution now; close it when
            # FunctionToolResultEvent arrives below.
            if tracing_handler is not None and isinstance(event.part, ToolCallPart) and event.part.tool_call_id:
                args: dict[str, Any] | str | None
                raw_args = event.part.args
                if isinstance(raw_args, dict):
                    args = dict(raw_args)
                elif isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args) if raw_args else {}
                    except json.JSONDecodeError:
                        args = {"_raw": raw_args}
                else:
                    args = {}
                await tracing_handler.on_tool_start(
                    tool_call_id=event.part.tool_call_id,
                    tool_name=event.part.tool_name,
                    arguments=args,
                )

        elif isinstance(event, FunctionToolResultEvent):
            result = event.part
            tool_call_id = result.tool_call_id
            tool_name = getattr(result, "tool_name", "") or ""
            message_index = next_message_index
            next_message_index += 1
            content_payload = _tool_return_content(result)
            yield StreamTaskMessageFull(
                type="full",
                index=message_index,
                content=ToolResponseContent(
                    type="tool_response",
                    author="agent",
                    tool_call_id=tool_call_id,
                    name=tool_name,
                    content=content_payload,
                ),
            )
            if tracing_handler is not None and tool_call_id:
                await tracing_handler.on_tool_end(
                    tool_call_id=tool_call_id,
                    result=content_payload,
                )

        elif isinstance(event, (FunctionToolCallEvent, FinalResultEvent, AgentRunResultEvent)):
            # Already covered by PartStart/PartDelta/PartEnd events above, or
            # informational only (FinalResultEvent / AgentRunResultEvent signal
            # run-level state, not new content to surface).
            continue

        else:
            logger.debug("Unhandled Pydantic AI event type: %r", type(event).__name__)
