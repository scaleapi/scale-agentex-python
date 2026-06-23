"""ClaudeCodeTurn — HarnessTurn implementation for the claude-code tap.

Wraps ``convert_claude_code_to_agentex_events`` to implement the
``HarnessTurn`` protocol: exposes ``events`` (the canonical
``StreamTaskMessage*`` stream) and ``usage()`` (the normalised
``TurnUsage``, populated after the stream is exhausted).

Usage normalization
-------------------
Claude Code's ``result`` envelope carries usage under several key shapes
depending on the CLI version. We defensive-map all known shapes:

    result.usage.input_tokens        -> input_tokens
    result.usage.output_tokens       -> output_tokens
    result.usage.cache_read_input_tokens
    result.usage.cache_creation_input_tokens  -> cached_input_tokens (sum)
    result.cost_usd / result.total_cost_usd   -> cost_usd
    result.duration_ms               -> duration_ms
    result.num_turns                 -> num_llm_calls

Real zeros are preserved; missing keys default to ``None`` (not zero) so
downstream consumers can distinguish "not reported" from "zero".

Out of scope: no deployable test agent is provided — see module docstring
in ``_claude_code_sync.py``.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from agentex.lib.core.harness.types import TurnUsage, HarnessTurn, StreamTaskMessage
from agentex.lib.adk._modules._claude_code_sync import convert_claude_code_to_agentex_events


def claude_code_usage_to_turn_usage(result_envelope: dict[str, Any]) -> TurnUsage:
    """Map a claude-code ``result`` envelope to a canonical ``TurnUsage``.

    Defensively handles missing / None values. Real zeros are preserved.
    ``cost_usd`` checks both ``cost_usd`` and ``total_cost_usd`` keys (the
    CLI has used both across versions).
    ``cached_input_tokens`` accumulates cache_read and cache_creation counts
    since both represent tokens served from the prompt cache.
    """
    usage_raw: dict[str, Any] = result_envelope.get("usage") or {}

    def _int(d: dict[str, Any], key: str) -> int | None:
        v = d.get(key)
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def _float(d: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            v = d.get(key)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    continue
        return None

    input_tokens = _int(usage_raw, "input_tokens")
    output_tokens = _int(usage_raw, "output_tokens")

    # Aggregate both cache_read and cache_creation into cached_input_tokens
    cache_read = _int(usage_raw, "cache_read_input_tokens")
    cache_creation = _int(usage_raw, "cache_creation_input_tokens")
    if cache_read is not None or cache_creation is not None:
        cached_input_tokens = (cache_read or 0) + (cache_creation or 0)
    else:
        cached_input_tokens = None

    total_tokens: int | None = None
    if input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    cost_usd = _float(result_envelope, "cost_usd", "total_cost_usd")
    duration_ms = _int(result_envelope, "duration_ms")

    # num_llm_calls is provider-reported (from num_turns): default None ("not
    # reported") rather than 0 so callers can distinguish it from a real zero,
    # matching the None convention used for the token fields above.
    num_turns = result_envelope.get("num_turns")
    num_llm_calls: int | None = None
    if num_turns is not None:
        try:
            num_llm_calls = int(num_turns)
        except (TypeError, ValueError):
            pass

    return TurnUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        num_llm_calls=num_llm_calls,
    )


class ClaudeCodeTurn:
    """HarnessTurn for a claude-code ``stream-json`` line stream.

    Satisfies the ``HarnessTurn`` protocol:
    - ``events`` yields the canonical ``StreamTaskMessage*`` stream.
    - ``usage()`` returns the normalised ``TurnUsage`` (only valid after
      ``events`` is fully consumed).

    ``lines`` is an async iterator of raw JSON strings or pre-parsed dicts, as
    produced by reading the claude-code CLI's stdout line by line.
    """

    def __init__(self, lines: AsyncIterator[str | dict[str, Any]]) -> None:
        self._lines = lines
        self._result_envelope: dict[str, Any] | None = None
        self._events_stream: AsyncIterator[StreamTaskMessage] | None = None

    async def _on_result(self, envelope: dict[str, Any]) -> None:
        self._result_envelope = envelope

    @property
    def events(self) -> AsyncIterator[StreamTaskMessage]:
        if self._events_stream is None:
            self._events_stream = convert_claude_code_to_agentex_events(
                self._lines,
                on_result=self._on_result,
            )
        return self._events_stream

    @property
    def session_id(self) -> str | None:
        """The Claude Code session id, for resuming a multi-turn session.

        Valid only after ``events`` has been fully consumed (populated by the
        ``result`` envelope). Returns ``None`` if the stream was truncated or
        Claude Code reported no session id.
        """
        if not self._result_envelope:
            return None
        return self._result_envelope.get("session_id")

    def usage(self) -> TurnUsage:
        """Return normalised usage for this turn.

        Call only after ``events`` is exhausted. Returns an empty ``TurnUsage``
        if the ``result`` envelope was not received (e.g. stream was truncated).
        """
        if self._result_envelope is None:
            return TurnUsage()
        return claude_code_usage_to_turn_usage(self._result_envelope)


# Runtime assert that ClaudeCodeTurn satisfies HarnessTurn protocol
assert isinstance(ClaudeCodeTurn.__new__(ClaudeCodeTurn), HarnessTurn), (
    "ClaudeCodeTurn must satisfy the HarnessTurn protocol"
)
