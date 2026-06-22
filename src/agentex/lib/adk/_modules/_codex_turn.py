"""CodexTurn: HarnessTurn implementation for the codex event-stream tap.

Wraps ``convert_codex_to_agentex_events`` so callers can pass a ``CodexTurn``
directly to ``UnifiedEmitter.yield_turn`` or ``UnifiedEmitter.auto_send_turn``.

Usage::

    from agentex.lib.adk import convert_codex_to_agentex_events
    from agentex.lib.adk._modules._codex_turn import CodexTurn, codex_usage_to_turn_usage

    turn = CodexTurn(events=codex_event_stream, model="o4-mini")
    async for msg in emitter.yield_turn(turn):
        yield msg
    turn_usage = turn.usage()

OUT OF SCOPE
------------
Like ``_codex_sync``, this module is a pure library tap. Subprocess
provisioning, sandbox setup, secret injection, and MCP configuration remain
in the golden agent (``teams/sgp/agents/golden_agent/project/harness/``).
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from agentex.lib.core.harness.types import TurnUsage
from agentex.lib.adk._modules._codex_sync import (
    StreamTaskMessage,
    convert_codex_to_agentex_events,
)


def codex_usage_to_turn_usage(
    raw: dict[str, Any] | None,
    *,
    model: str | None = None,
    tool_call_count: int = 0,
    reasoning_count: int = 0,
    duration_ms: int | None = None,
    cost_usd: float | None = None,
) -> TurnUsage:
    """Map a raw codex ``turn.completed`` usage dict to a canonical ``TurnUsage``.

    Codex reports token usage under the ``usage`` key of the
    ``turn.completed`` event. The shape follows the OpenAI completion_tokens
    convention because codex is built on OpenAI models:

    .. code-block:: json

        {
            "input_tokens": 1234,
            "output_tokens": 456,
            "total_tokens": 1690
        }

    Additionally, codex may report ``reasoning_tokens`` for o-series models:

    .. code-block:: json

        {
            "input_tokens": 1234,
            "output_tokens": 456,
            "reasoning_tokens": 200,
            "total_tokens": 1690
        }

    Defensive rules:
    - Missing ``raw`` or missing sub-keys default to ``None`` (not zero) so
      downstream callers can distinguish "not reported" from "reported as 0".
    - Real zeros (``0`` explicitly present in ``raw``) are preserved as ``0``.
    - ``total_tokens`` is accepted from the payload or left as ``None``;
      callers should not recompute it because codex may use cached tokens.
    - ``cost_usd`` is passed through when codex reports it (not yet common);
      defaults to ``None`` if absent.

    Args:
        raw: The raw codex usage dict from ``turn.completed``, or ``None``.
        model: Model string (e.g. "o4-mini") to attach to the usage record.
        tool_call_count: Number of tool calls in the turn (from processor).
        reasoning_count: Number of reasoning blocks (from processor).
        duration_ms: Wall-clock duration of the turn in milliseconds.
        cost_usd: Cost in USD if the caller can derive it; ``None`` otherwise.

    Returns:
        A populated ``TurnUsage`` instance.
    """
    if not isinstance(raw, dict):
        raw = {}

    def _int_or_none(key: str) -> int | None:
        val = raw.get(key)
        if val is None:
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    def _float_or_none(key: str) -> float | None:
        val = raw.get(key)
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    # cost_usd: prefer explicitly passed value, then fall back to raw payload.
    effective_cost = cost_usd if cost_usd is not None else _float_or_none("cost_usd")

    return TurnUsage(
        model=model or None,
        input_tokens=_int_or_none("input_tokens"),
        output_tokens=_int_or_none("output_tokens"),
        cached_input_tokens=_int_or_none("cached_input_tokens"),
        reasoning_tokens=_int_or_none("reasoning_tokens"),
        total_tokens=_int_or_none("total_tokens"),
        cost_usd=effective_cost,
        duration_ms=duration_ms,
        num_llm_calls=1,
        num_tool_calls=tool_call_count,
        num_reasoning_blocks=reasoning_count,
    )


class CodexTurn:
    """A single codex turn as a ``HarnessTurn``.

    Implements the ``HarnessTurn`` protocol so it can be passed to
    ``UnifiedEmitter.yield_turn`` and ``UnifiedEmitter.auto_send_turn``.

    ``usage()`` is valid only after ``events`` has been fully consumed (i.e.
    the async generator has been exhausted). Calling ``usage()`` before
    exhaustion returns a zero-value ``TurnUsage`` with only ``model`` set.

    Args:
        events: An async iterator of ``str | dict`` codex events, as
            produced by reading ``codex exec --json`` stdout line by line.
        model: Model string to attach to the ``TurnUsage``.
        duration_ms: Optional turn wall-clock duration in milliseconds.
        cost_usd: Optional cost in USD; ``None`` if not known.
    """

    def __init__(
        self,
        events: AsyncIterator[str | dict[str, Any]],
        *,
        model: str | None = None,
        duration_ms: int | None = None,
        cost_usd: float | None = None,
    ) -> None:
        self._raw_events = events
        self._model = model
        # Public + mutable: the true wall-clock duration (and cost) is usually
        # only known after the stream is consumed, so callers may set these
        # after construction and before calling usage().
        self.duration_ms = duration_ms
        self.cost_usd = cost_usd

        # Populated by the on_result callback once the stream is exhausted.
        self._result: dict[str, Any] | None = None
        # The events generator is created at most once: ``_raw_events`` is a
        # single-consumption AsyncIterator, so re-wrapping it would yield an
        # already-exhausted stream that fires on_result with zeros and clobbers
        # ``_result``. Cache the generator and hand back the same instance.
        self._events_gen: AsyncIterator[StreamTaskMessage] | None = None

    @property
    def events(self) -> AsyncIterator[StreamTaskMessage]:
        """Async iterator of canonical ``StreamTaskMessage*`` events.

        The ``on_result`` callback populates ``_result`` when the underlying
        codex stream ends, so ``usage()`` returns meaningful data after
        exhaustion. Returns the same generator on every access so the underlying
        stream is consumed (and ``on_result`` fires) exactly once.
        """
        if self._events_gen is None:
            self._events_gen = convert_codex_to_agentex_events(
                self._raw_events,
                on_result=self._on_result,
            )
        return self._events_gen

    def _on_result(self, result: dict[str, Any]) -> None:
        self._result = result

    def usage(self) -> TurnUsage:
        """Return normalized ``TurnUsage`` for this turn.

        Valid only after ``events`` has been fully consumed. Returns a
        zero-value ``TurnUsage`` (model set, counts zero, tokens None) if
        called before the stream ends.
        """
        if self._result is None:
            return TurnUsage(model=self._model)
        return codex_usage_to_turn_usage(
            self._result.get("usage"),
            model=self._model,
            tool_call_count=self._result.get("tool_call_count", 0),
            reasoning_count=self._result.get("reasoning_count", 0),
            duration_ms=self.duration_ms,
            cost_usd=self.cost_usd,
        )
