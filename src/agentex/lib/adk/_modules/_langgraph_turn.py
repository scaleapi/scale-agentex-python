"""HarnessTurn adapter for LangGraph astream() event streams.

Provides ``LangGraphTurn`` (a ``HarnessTurn`` implementation) and the
``langgraph_usage_to_turn_usage`` helper that maps LangGraph's
``AIMessage.usage_metadata`` onto the framework-agnostic ``TurnUsage`` model.

AGX1-377 note: LangGraph emits tool requests as ``StreamTaskMessageFull`` events
(from "updates" events), NOT Start+Delta+Done like pydantic-ai. ``auto_send``
handles Full events correctly; no coalescing wrapper is needed.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from agentex.lib.core.harness.types import TurnUsage, StreamTaskMessage
from agentex.lib.adk._modules._langgraph_sync import convert_langgraph_to_agentex_events


def langgraph_usage_to_turn_usage(usage_metadata: Any, model: str | None) -> TurnUsage:
    """Map LangGraph ``AIMessage.usage_metadata`` onto ``TurnUsage``.

    ``usage_metadata`` may be ``None`` (model doesn't report usage).
    Real zero token counts (e.g. 0 output tokens) are preserved as 0, NOT
    coerced to ``None``.

    Mapping::

        input_tokens                       -> input_tokens
        output_tokens                      -> output_tokens
        total_tokens                       -> total_tokens
        input_token_details.cache_read     -> cached_input_tokens
        output_token_details.reasoning     -> reasoning_tokens

    Args:
        usage_metadata: The ``usage_metadata`` dict from an ``AIMessage``,
            or ``None`` if the model did not report usage.
        model: The model name string to attach to the ``TurnUsage``, or ``None``.

    Returns:
        A populated ``TurnUsage`` instance.
    """
    if usage_metadata is None:
        return TurnUsage(model=model)

    raw_input = (usage_metadata or {}).get("input_tokens")
    raw_output = (usage_metadata or {}).get("output_tokens")
    raw_total = (usage_metadata or {}).get("total_tokens")
    input_details = (usage_metadata or {}).get("input_token_details") or {}
    output_details = (usage_metadata or {}).get("output_token_details") or {}
    raw_cache_read = input_details.get("cache_read")
    raw_reasoning = output_details.get("reasoning")

    return TurnUsage(
        model=model,
        input_tokens=raw_input,
        output_tokens=raw_output,
        total_tokens=raw_total,
        cached_input_tokens=raw_cache_read,
        reasoning_tokens=raw_reasoning,
    )


class LangGraphTurn:
    """HarnessTurn wrapping a LangGraph ``astream()`` event stream.

    Implements the ``HarnessTurn`` Protocol so it can be passed to either
    ``UnifiedEmitter.yield_turn`` (sync HTTP ACP) or
    ``UnifiedEmitter.auto_send_turn`` (async / temporal).

    Usage::

        stream = graph.astream(
            {"messages": [{"role": "user", "content": user_message}]},
            stream_mode=["messages", "updates"],
        )
        turn = LangGraphTurn(stream, model=model_name)

        # Sync HTTP ACP
        async for event in emitter.yield_turn(turn):
            yield event

        # Async / temporal
        result = await emitter.auto_send_turn(turn)

    AGX1-377 note: LangGraph tool requests are ``StreamTaskMessageFull`` (from
    "updates"), NOT Start+Delta+Done like pydantic-ai. No ``coalesce_tool_requests``
    option is needed.

    Usage data is captured lazily via the ``on_final_ai_message`` callback and
    is only valid after ``events`` has been fully consumed.
    """

    def __init__(self, stream: Any, model: str | None = None) -> None:
        self._stream = stream
        self._model = model
        self._usage: TurnUsage = TurnUsage(model=model)

    @property
    def events(self) -> AsyncIterator[StreamTaskMessage]:
        return self._generate_events()

    async def _generate_events(self) -> AsyncIterator[StreamTaskMessage]:
        def _capture(ai_msg: Any) -> None:
            usage_metadata = getattr(ai_msg, "usage_metadata", None)
            if usage_metadata is not None:
                self._usage = langgraph_usage_to_turn_usage(usage_metadata, self._model)

        async for ev in convert_langgraph_to_agentex_events(self._stream, on_final_ai_message=_capture):
            yield ev

    def usage(self) -> TurnUsage:
        """Return the usage captured from the last AIMessage in the stream.

        Valid only after ``events`` has been fully consumed.
        Returns a zero-usage ``TurnUsage`` if the model did not report usage.
        """
        return self._usage
