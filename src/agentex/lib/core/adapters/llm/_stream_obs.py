"""Shared GenAI-streaming instrumentation for the LLM adapters.

Both the litellm and scale-gp gateways yield the same OpenAI-shaped ``Completion``
chunk, so one set of extractors + attribute builders drives
``sgp_obs.traces.instrument_stream`` for both. Every extractor is defensive — an
obs helper must never raise into the token stream.
"""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from agentex.lib.types.llm_messages import Completion


def delta_content(chunk: Completion) -> Any:
    """Text delta of a streaming chunk, or ``None`` — tolerant of provider shape."""
    try:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            return None
        delta = getattr(choices[0], "delta", None)
        return getattr(delta, "content", None) if delta is not None else None
    except Exception:
        return None


def output_tokens(chunk: Completion) -> int:
    # 1 per content-bearing delta — a good streaming proxy without a tokenizer.
    return 1 if delta_content(chunk) else 0


def is_answer(chunk: Completion) -> bool:
    # First user-visible answer token (text); skips role-only / tool-call / empty deltas.
    return bool(delta_content(chunk))


def stream_attrs(system: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Mapping[str, Any]:
    """GenAI-semconv attributes for the ``gen_ai.chat`` span. ``model`` is read from
    kwargs or the first positional arg, matching how the gateways call the client."""
    model = kwargs.get("model") or (args[0] if args else None)
    attrs: dict[str, Any] = {"gen_ai.system": system, "gen_ai.operation.name": "chat"}
    if model:
        attrs["gen_ai.request.model"] = str(model)
    return attrs
