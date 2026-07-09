"""Helpers for putting LLM token usage onto trace spans in the billable shape.

The AgentEx backend bills token usage from ``application_trace_span`` rows using
two span fields:

- ``span.data["usage"]`` (+ ``span.data["cost_usd"]``): the per-turn AGGREGATE.
  Emit at most once per turn, holding that turn's own (per-invocation, not
  session-cumulative) usage. When a trace contains an aggregate, the backend
  keeps it and drops all per-call spans in that trace.
- ``span.output["usage"]``: per-call detail. Summed by the backend, and dropped
  whenever an aggregate exists in the trace.

Never emit usage on both a rollup span and its per-call children via
``output["usage"]`` — that double-counts.

Recognized token key spellings (either spelling of a pair works):
``input_tokens``/``prompt_tokens``, ``output_tokens``/``completion_tokens``,
``cached_input_tokens``/``cached_tokens``, ``reasoning_tokens``; cost is
``cost_usd``.
"""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

# Key spellings the backend accepts when summing token usage from spans.
RECOGNIZED_USAGE_KEYS = frozenset(
    {
        "input_tokens",
        "prompt_tokens",
        "output_tokens",
        "completion_tokens",
        "cached_input_tokens",
        "cached_tokens",
        "reasoning_tokens",
        "total_tokens",
        "cost_usd",
    }
)


def usage_from_counts(
    *,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    cached_input_tokens: int | None = None,
    reasoning_tokens: int | None = None,
    cost_usd: float | None = None,
) -> dict[str, Any]:
    """Build a usage blob with canonical key spellings, omitting None values."""
    usage: dict[str, Any] = {}
    if input_tokens is not None:
        usage["input_tokens"] = input_tokens
    if output_tokens is not None:
        usage["output_tokens"] = output_tokens
    if total_tokens is not None:
        usage["total_tokens"] = total_tokens
    if cached_input_tokens is not None:
        usage["cached_input_tokens"] = cached_input_tokens
    if reasoning_tokens is not None:
        usage["reasoning_tokens"] = reasoning_tokens
    if cost_usd is not None:
        usage["cost_usd"] = cost_usd
    return usage


def usage_from_openai_response_usage(usage: Any) -> dict[str, Any] | None:
    """Extract a usage blob from an OpenAI-style usage object.

    Duck-typed so it works for both ``agents.usage.Usage`` (OpenAI Agents SDK)
    and ``openai.types.responses.ResponseUsage``: reads ``input_tokens``,
    ``output_tokens``, ``total_tokens``, ``input_tokens_details.cached_tokens``,
    and ``output_tokens_details.reasoning_tokens``.

    Returns None when there is nothing usable to report.
    """
    if usage is None:
        return None

    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    if input_tokens is None and output_tokens is None:
        return None

    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    return usage_from_counts(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=getattr(usage, "total_tokens", None),
        cached_input_tokens=getattr(input_details, "cached_tokens", None) if input_details is not None else None,
        reasoning_tokens=getattr(output_details, "reasoning_tokens", None) if output_details is not None else None,
    )


def validate_usage_blob(usage: Mapping[str, Any]) -> dict[str, Any]:
    """Return the usage mapping as a plain dict, warning on unrecognized shapes.

    The blob is passed through untouched so callers keep full control; the
    warning catches typos (e.g. ``inputTokens``) that the backend would
    silently ignore when billing.
    """
    blob = dict(usage)
    if not any(key in RECOGNIZED_USAGE_KEYS for key in blob):
        logger.warning(
            "Usage blob has no recognized token keys and will not be billed. "
            f"Got keys {sorted(blob)}; expected any of {sorted(RECOGNIZED_USAGE_KEYS)}."
        )
    return blob
