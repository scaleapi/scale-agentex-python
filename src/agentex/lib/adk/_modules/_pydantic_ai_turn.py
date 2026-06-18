"""PydanticAITurn: a HarnessTurn wrapping a pydantic-ai event stream.

Adapts a pydantic-ai ``AgentStreamEvent`` stream into the canonical
``StreamTaskMessage*`` stream while capturing run-level usage from the
terminal ``AgentRunResultEvent``.

Typical usage::

    async with agent.run_stream_events(user_msg) as stream:
        turn = PydanticAITurn(stream, model="openai:gpt-4o")
        async for event in turn.events:
            yield event
        span.set_attributes(turn.usage().model_dump())
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, AsyncIterator

from pydantic_ai.run import AgentRunResultEvent

from agentex.lib.core.harness.types import TurnUsage
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.lib.adk._modules._pydantic_ai_sync import convert_pydantic_ai_to_agentex_events

if TYPE_CHECKING:
    from agentex.lib.adk._modules._pydantic_ai_tracing import AgentexPydanticAITracingHandler

StreamTaskMessage = StreamTaskMessageStart | StreamTaskMessageDelta | StreamTaskMessageFull | StreamTaskMessageDone


def pydantic_ai_usage_to_turn_usage(usage: Any, model: str | None) -> TurnUsage:
    """Map a pydantic-ai ``RunUsage`` onto ``TurnUsage``.

    Uses defensive ``getattr(..., None)`` so a future field rename in
    pydantic-ai degrades to ``None`` rather than raising ``AttributeError``.

    RunUsage fields (verified against pydantic-ai in this repo):
        input_tokens, cache_write_tokens, cache_read_tokens, output_tokens,
        input_audio_tokens, cache_audio_read_tokens, output_audio_tokens,
        details, requests, tool_calls.
    ``total_tokens`` is a computed property.

    Mapping:
        requests           -> num_llm_calls
        input_tokens       -> input_tokens
        output_tokens      -> output_tokens
        cache_read_tokens  -> cached_input_tokens
        total_tokens       -> total_tokens

    getattr results pass straight through: a MISSING attribute degrades to
    None (defensive), while a real 0 stays 0 (a cache-hit with 0 output
    tokens is a genuine zero, not "unknown") and a real N stays N.
    """
    raw_input = getattr(usage, "input_tokens", None)
    raw_output = getattr(usage, "output_tokens", None)
    raw_cache_read = getattr(usage, "cache_read_tokens", None)
    raw_total = getattr(usage, "total_tokens", None)
    raw_requests = getattr(usage, "requests", None)

    return TurnUsage(
        model=model,
        input_tokens=raw_input,
        output_tokens=raw_output,
        cached_input_tokens=raw_cache_read,
        total_tokens=raw_total,
        num_llm_calls=raw_requests if raw_requests is not None else 0,
    )


async def _coalesce_tool_requests(
    source: AsyncIterator[StreamTaskMessage],
) -> AsyncIterator[StreamTaskMessage]:
    """Convert Start(tool_request)+deltas+Done into Full(tool_request).

    ``convert_pydantic_ai_to_agentex_events`` emits ``Start+Done`` for tool
    calls (enabling streaming of argument tokens over the sync/HTTP channel).
    The async/auto_send delivery path does not stream tool-call arguments —
    it uses Option A (full messages). This wrapper coalesces the Start+Done
    sequence into a single ``StreamTaskMessageFull``, matching the shape that
    ``auto_send`` expects and that the harness conformance tests are designed for.

    Argument delta fragments (``ToolRequestDelta.arguments_delta``) are
    accumulated as a JSON string and parsed back into a dict. If parsing
    fails, the raw string is stored under ``"_raw"`` so no information is lost.
    """
    from agentex.types.tool_request_delta import ToolRequestDelta
    from agentex.types.tool_request_content import ToolRequestContent

    # pending[index] = (ToolRequestContent, accumulated_args_delta_str)
    pending: dict[Any, tuple[Any, str]] = {}

    async for event in source:
        if isinstance(event, StreamTaskMessageStart):
            ctype = getattr(event.content, "type", None)
            if ctype == "tool_request":
                # Stage; do not yield — replaced by Full on Done.
                pending[event.index] = (event.content, "")
                continue

        elif isinstance(event, StreamTaskMessageDelta):
            if event.index in pending and isinstance(event.delta, ToolRequestDelta):
                # Accumulate argument delta fragments; don't yield.
                content, accum = pending[event.index]
                pending[event.index] = (content, accum + (event.delta.arguments_delta or ""))
                continue

        elif isinstance(event, StreamTaskMessageDone):
            if event.index in pending:
                content, args_delta = pending.pop(event.index)
                # Build final arguments: merge initial dict with accumulated delta.
                base_args: dict[str, Any] = {}
                if isinstance(content, ToolRequestContent):
                    base_args = dict(content.arguments) if content.arguments else {}

                if args_delta:
                    try:
                        parsed = json.loads(args_delta)
                        if isinstance(parsed, dict):
                            base_args.update(parsed)
                        else:
                            base_args["_raw"] = args_delta
                    except json.JSONDecodeError:
                        base_args["_raw"] = args_delta

                # Emit as Full with the complete arguments.
                full_content = (
                    ToolRequestContent(
                        type="tool_request",
                        author=content.author if isinstance(content, ToolRequestContent) else "agent",
                        tool_call_id=content.tool_call_id if isinstance(content, ToolRequestContent) else "",
                        name=content.name if isinstance(content, ToolRequestContent) else "",
                        arguments=base_args,
                    )
                    if isinstance(content, ToolRequestContent)
                    else content
                )
                yield StreamTaskMessageFull(type="full", index=event.index, content=full_content)
                continue

        yield event


class PydanticAITurn:
    """A single harness turn backed by a pydantic-ai event stream.

    Satisfies the ``HarnessTurn`` protocol: ``events`` async-generates the
    canonical ``StreamTaskMessage*`` stream; ``usage()`` returns a normalized
    ``TurnUsage`` (valid only after ``events`` is exhausted).

    By default ``events`` is identical to the bare
    ``convert_pydantic_ai_to_agentex_events`` output (tool calls stream as
    ``Start + ToolRequestDelta + Done``, preserving argument-token streaming on
    the sync/yield channel). When ``coalesce_tool_requests=True``, tool-request
    sequences are collapsed into a single ``StreamTaskMessageFull`` (Option A —
    no streaming of argument tokens) for the async/auto_send path.
    """

    def __init__(
        self,
        stream: AsyncIterator[Any],
        model: str | None = None,
        tracing_handler: "AgentexPydanticAITracingHandler | None" = None,
        coalesce_tool_requests: bool = False,
    ) -> None:
        self._stream = stream
        self._model = model
        self._tracing_handler = tracing_handler
        self._coalesce_tool_requests = coalesce_tool_requests
        self._usage = TurnUsage(model=model)

    @property
    def events(self) -> AsyncIterator[StreamTaskMessage]:
        return self._generate_events()

    async def _generate_events(self) -> AsyncIterator[StreamTaskMessage]:
        def _capture(result_event: AgentRunResultEvent) -> None:
            run_result = getattr(result_event, "result", None)
            if run_result is None:
                return
            usage_attr = getattr(run_result, "usage", None)
            if usage_attr is None:
                return
            # In newer pydantic-ai, .usage is a DeprecatedCallableRunUsage —
            # it's both a property value and callable (emitting a deprecation
            # warning when called). Access it as a plain attribute to avoid the
            # warning; it already IS the RunUsage instance.
            usage_obj = usage_attr
            self._usage = pydantic_ai_usage_to_turn_usage(usage_obj, self._model)

        raw_stream = convert_pydantic_ai_to_agentex_events(
            self._stream,
            tracing_handler=self._tracing_handler,
            on_result=_capture,
        )
        if self._coalesce_tool_requests:
            async for ev in _coalesce_tool_requests(raw_stream):
                yield ev
        else:
            async for ev in raw_stream:
                yield ev

    def usage(self) -> TurnUsage:
        """Return the normalized usage for this turn.

        Valid only after ``events`` is exhausted (single-pass contract).
        Before exhaustion the model field is set but token fields are None.
        """
        return self._usage
