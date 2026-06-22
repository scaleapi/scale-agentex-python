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

from typing import Any, AsyncIterator

from pydantic_ai.run import AgentRunResultEvent

from agentex.lib.core.harness.types import TurnUsage
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.lib.adk._modules._pydantic_ai_sync import convert_pydantic_ai_to_agentex_events

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


class PydanticAITurn:
    """A single harness turn backed by a pydantic-ai event stream.

    Satisfies the ``HarnessTurn`` protocol: ``events`` async-generates the
    canonical ``StreamTaskMessage*`` stream; ``usage()`` returns a normalized
    ``TurnUsage`` (valid only after ``events`` is exhausted).

    ``events`` is identical to the bare ``convert_pydantic_ai_to_agentex_events``
    output (tool calls stream as ``Start + ToolRequestDelta + Done``, preserving
    argument-token streaming on the sync/yield channel). The foundation
    ``auto_send`` delivers the streamed tool-request shape natively, so no
    coalescing is needed on either channel.
    """

    def __init__(
        self,
        stream: AsyncIterator[Any],
        model: str | None = None,
    ) -> None:
        self._stream = stream
        self._model = model
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
            on_result=_capture,
        )
        async for ev in raw_stream:
            yield ev

    def usage(self) -> TurnUsage:
        """Return the normalized usage for this turn.

        Valid only after ``events`` is exhausted (single-pass contract).
        Before exhaustion the model field is set but token fields are None.
        """
        return self._usage
