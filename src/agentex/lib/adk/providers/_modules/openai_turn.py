"""OpenAITurn: adapt an OpenAI Agents SDK streamed run onto the harness surface.

A ``HarnessTurn`` exposes a single canonical ``StreamTaskMessage*`` stream plus
normalized usage. ``OpenAITurn`` wraps a ``RunResultStreaming`` (from
``Runner.run_streamed``), converts its native OpenAI events into the canonical
stream via ``convert_openai_to_agentex_events``, and after exhaustion reads the
run's ``raw_responses`` to aggregate usage into a provider-independent
``TurnUsage``.

Delivery (yield vs auto-send) and tracing are owned by ``UnifiedEmitter``; this
module is purely the provider->canonical adapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator

from agents.usage import Usage

from agentex.lib.utils.logging import make_logger
from agentex.lib.core.harness.types import TurnUsage, StreamTaskMessage
from agentex.lib.adk.providers._modules.sync_provider import (
    convert_openai_to_agentex_events,
)

if TYPE_CHECKING:
    from agents import ModelResponse, RunResultStreaming

logger = make_logger(__name__)


def openai_usage_to_turn_usage(usage: Usage | None, model: str | None) -> TurnUsage:
    """Map an ``agents.Usage`` to a harness-independent ``TurnUsage``.

    All field access is defensive (``getattr(..., None)``): different model
    backends populate different subsets of the usage object, and real zeros are
    valid values (e.g. 0 output tokens on a pure cache hit), so we never coerce
    a present-but-zero value into ``None``.
    """
    if usage is None:
        return TurnUsage(model=model)

    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)

    return TurnUsage(
        model=model,
        num_llm_calls=getattr(usage, "requests", None) or 0,
        input_tokens=getattr(usage, "input_tokens", None),
        cached_input_tokens=getattr(input_details, "cached_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        reasoning_tokens=getattr(output_details, "reasoning_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
    )


def _aggregate_usage(raw_responses: list[ModelResponse]) -> Usage | None:
    """Sum the per-response ``Usage`` across a run's ``ModelResponse`` list.

    Returns ``None`` when no response carries usage so the caller can emit a
    usage object with only the model name set. ``Usage.add`` accumulates
    requests/tokens (including cached/reasoning detail fields).
    """
    total: Usage | None = None
    for response in raw_responses:
        resp_usage = getattr(response, "usage", None)
        if resp_usage is None:
            continue
        if total is None:
            total = Usage()
        total.add(resp_usage)
    return total


class OpenAITurn:
    """A single OpenAI Agents SDK turn adapted to the ``HarnessTurn`` protocol.

    Construct with exactly one of:
    - ``result``: a ``RunResultStreaming`` from ``Runner.run_streamed``. Its
      ``stream_events()`` is converted to the canonical stream, and after the
      stream is exhausted ``raw_responses`` is read to compute usage.
    - ``stream``: a pre-built async iterator of canonical ``StreamTaskMessage``
      events (bypasses ``convert_openai_to_agentex_events``). Useful for tests
      and for callers that have already produced canonical events. Usage stays
      at ``TurnUsage(model=...)`` because there is no run to read usage from.

    ``coalesce_tool_requests`` is accepted for API parity with other provider
    turns but is a no-op for OpenAI: the OpenAI converter already emits a single
    ``Full(ToolRequestContent)`` per tool call rather than streamed argument
    deltas, so there is nothing to coalesce.
    """

    def __init__(
        self,
        result: RunResultStreaming | None = None,
        model: str | None = None,
        stream: AsyncIterator[StreamTaskMessage] | None = None,
        coalesce_tool_requests: bool = False,  # noqa: ARG002 - API parity, no-op for OpenAI
    ) -> None:
        if result is None and stream is None:
            raise ValueError("OpenAITurn requires either `result` or `stream`")
        self._result = result
        self._model = model
        self._stream = stream
        self._usage: TurnUsage = TurnUsage(model=model)

    @property
    def events(self) -> AsyncIterator[StreamTaskMessage]:
        return self._iter_events()

    async def _iter_events(self) -> AsyncIterator[StreamTaskMessage]:
        if self._stream is not None:
            async for event in self._stream:
                yield event
            return

        result = self._result
        assert result is not None  # guaranteed by __init__
        async for event in convert_openai_to_agentex_events(result.stream_events()):
            yield event

        # Stream is exhausted: the run has finished and raw_responses is now
        # populated, so usage can be aggregated and normalized.
        try:
            raw_responses: list[Any] = list(getattr(result, "raw_responses", None) or [])
            aggregated = _aggregate_usage(raw_responses)
            self._usage = openai_usage_to_turn_usage(aggregated, self._model)
        except Exception as exc:  # pragma: no cover - defensive: never break delivery on usage
            logger.warning(f"Failed to aggregate OpenAI usage: {exc}")
            self._usage = TurnUsage(model=self._model)

    def usage(self) -> TurnUsage:
        """Normalized turn usage. Valid only after ``events`` is exhausted."""
        return self._usage
