"""GeminiCliTurn — HarnessTurn implementation for the Gemini CLI tap.

Wraps ``convert_gemini_cli_to_agentex_events`` to implement the
``HarnessTurn`` protocol: exposes ``events`` (the canonical
``StreamTaskMessage*`` stream) and ``usage()`` (the normalised ``TurnUsage``,
populated after the stream is exhausted).

Usage normalization
-------------------
The CLI's terminal ``result`` event carries ``stats``:

    stats.input_tokens   -> input_tokens
    stats.output_tokens  -> output_tokens
    stats.cached         -> cached_input_tokens
    stats.total_tokens   -> total_tokens (or input + output when absent)
    stats.duration_ms    -> duration_ms
    stats.tool_calls     -> num_tool_calls
    init.model / stats.models -> model

The CLI does not report cost or the number of model calls, so ``cost_usd``
and ``num_llm_calls`` stay ``None``. Real zeros are preserved; missing keys
default to ``None`` so consumers can tell "not reported" from "zero".
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from agentex.lib.core.harness.types import TurnUsage, HarnessTurn, StreamTaskMessage
from agentex.lib.adk._modules._gemini_cli_sync import convert_gemini_cli_to_agentex_events


def gemini_cli_usage_to_turn_usage(result_envelope: dict[str, Any], model: str | None = None) -> TurnUsage:
    """Map a Gemini CLI ``result`` event to a canonical ``TurnUsage``.

    ``model`` (from the ``init`` event) wins; otherwise the first model named
    under ``stats.models`` is used. Missing values map to ``None``.
    """
    stats: dict[str, Any] = result_envelope.get("stats") or {}

    def _int(d: dict[str, Any], key: str) -> int | None:
        v = d.get(key)
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    input_tokens = _int(stats, "input_tokens")
    output_tokens = _int(stats, "output_tokens")
    cached_input_tokens = _int(stats, "cached")
    total_tokens = _int(stats, "total_tokens")
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    duration_ms = _int(stats, "duration_ms")
    num_tool_calls = _int(stats, "tool_calls") or 0

    if model is None:
        models = stats.get("models")
        if isinstance(models, dict) and models:
            model = next(iter(models))

    return TurnUsage(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        total_tokens=total_tokens,
        duration_ms=duration_ms,
        num_tool_calls=num_tool_calls,
    )


class GeminiCliTurn:
    """HarnessTurn for a Gemini CLI ``stream-json`` line stream.

    Satisfies the ``HarnessTurn`` protocol:
    - ``events`` yields the canonical ``StreamTaskMessage*`` stream.
    - ``usage()`` returns the normalised ``TurnUsage`` (only valid after
      ``events`` is fully consumed).

    ``lines`` is an async iterator of raw JSON strings or pre-parsed dicts, as
    produced by reading the ``gemini`` CLI's stdout line by line.
    """

    def __init__(self, lines: AsyncIterator[str | dict[str, Any]]) -> None:
        self._lines = lines
        self._result_envelope: dict[str, Any] | None = None
        self._session_id: str | None = None
        self._model: str | None = None
        self._events_stream: AsyncIterator[StreamTaskMessage] | None = None

    async def _on_result(self, envelope: dict[str, Any]) -> None:
        self._result_envelope = envelope

    async def _on_init(self, envelope: dict[str, Any]) -> None:
        sid = envelope.get("session_id")
        if sid:
            self._session_id = str(sid)
        model = envelope.get("model")
        if model:
            self._model = str(model)

    @property
    def events(self) -> AsyncIterator[StreamTaskMessage]:
        if self._events_stream is None:
            self._events_stream = convert_gemini_cli_to_agentex_events(
                self._lines,
                on_result=self._on_result,
                on_init=self._on_init,
            )
        return self._events_stream

    @property
    def session_id(self) -> str | None:
        """The Gemini CLI session id from the ``init`` event, if reported."""
        return self._session_id

    @property
    def model(self) -> str | None:
        """The model name from the ``init`` event, if reported."""
        return self._model

    def usage(self) -> TurnUsage:
        """Return normalised usage for this turn.

        Call only after ``events`` is exhausted. Returns an empty ``TurnUsage``
        if the ``result`` event was not received (e.g. the stream was truncated).
        """
        if self._result_envelope is None:
            return TurnUsage(model=self._model)
        return gemini_cli_usage_to_turn_usage(self._result_envelope, model=self._model)


# Runtime assert that GeminiCliTurn satisfies the HarnessTurn protocol
assert isinstance(GeminiCliTurn.__new__(GeminiCliTurn), HarnessTurn), (
    "GeminiCliTurn must satisfy the HarnessTurn protocol"
)
