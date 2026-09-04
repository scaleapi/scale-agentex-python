"""OTel metrics for LLM calls.

Single source of truth for LLM-call instrumentation across all agentex code
paths — temporal+openai_agents streaming today, sync ACP and the Claude SDK
plugin in future PRs. Centralizing the instrument definitions here means
those follow-ups don't need to redefine the metric names, units, or
description strings; they import ``get_llm_metrics()`` and record values.

The meter is no-op when the application hasn't configured a ``MeterProvider``,
so importing this module is safe for runtimes that don't use OTel. Instruments
are created lazily on first ``get_llm_metrics()`` call so a ``MeterProvider``
configured *after* this module is imported still binds correctly.

Cardinality is bounded:
- All metrics carry only ``model`` (the LLM model name).
- ``requests`` additionally carries ``status``, drawn from a small fixed set
  (see ``classify_status``).

Resource attributes (``service.name``, ``k8s.*``, etc.) come from the
application's OTel resource configuration and are added to every series
automatically.
"""

from __future__ import annotations

from typing import Optional

from opentelemetry import metrics


class LLMMetrics:
    """Lazily-created OTel instruments for LLM call telemetry."""

    def __init__(self) -> None:
        meter = metrics.get_meter("agentex.llm")
        self.requests = meter.create_counter(
            name="agentex.llm.requests",
            unit="1",
            description=(
                "LLM call count tagged with status (success / rate_limit / "
                "server_error / client_error / timeout / network_error / "
                "other_error). Use to alert on 429s, 5xxs, etc."
            ),
        )
        self.ttft_ms = meter.create_histogram(
            name="agentex.llm.ttft",
            unit="ms",
            description="Time from request submission to first content token (ms)",
        )
        # ttat (time-to-first-answering-token) is distinct from ttft for reasoning
        # models: ttft fires on the first reasoning chunk (which arrives quickly),
        # while ttat fires on the first user-visible answer token (text or tool
        # call). For non-reasoning models the two are equal.
        self.ttat_ms = meter.create_histogram(
            name="agentex.llm.ttat",
            unit="ms",
            description="Time from request submission to first answering token (text or tool-call delta) — excludes reasoning chunks",
        )
        # Note: TPS denominator is the model-generation window
        # (last_token_time - first_token_time), not total stream wall time.
        # This isolates raw model throughput from event-loop / tool-call latency.
        self.tps = meter.create_histogram(
            name="agentex.llm.tps",
            unit="tokens/s",
            description="Output tokens per second over the generation window",
        )
        self.input_tokens = meter.create_counter(
            name="agentex.llm.input_tokens",
            unit="tokens",
            description="Total input tokens sent to the LLM",
        )
        self.output_tokens = meter.create_counter(
            name="agentex.llm.output_tokens",
            unit="tokens",
            description="Total output tokens returned by the LLM",
        )
        self.cached_input_tokens = meter.create_counter(
            name="agentex.llm.cached_input_tokens",
            unit="tokens",
            description="Subset of input tokens served from prompt cache",
        )
        self.reasoning_tokens = meter.create_counter(
            name="agentex.llm.reasoning_tokens",
            unit="tokens",
            description="Output tokens spent on reasoning (subset of output_tokens)",
        )


_llm_metrics: Optional[LLMMetrics] = None


def get_llm_metrics() -> LLMMetrics:
    """Return the LLM metrics singleton, creating it on first use."""
    global _llm_metrics
    if _llm_metrics is None:
        _llm_metrics = LLMMetrics()
    return _llm_metrics


def classify_status(exc: Optional[BaseException]) -> str:
    """Categorize an LLM call's outcome into a small fixed set of status labels.

    A successful call returns ``"success"``. Exceptions are mapped by type name
    so we don't depend on a specific provider SDK's exception class hierarchy:
    OpenAI, Anthropic, and other providers all use names like ``RateLimitError``,
    ``APITimeoutError``, ``InternalServerError``, etc.
    """
    if exc is None:
        return "success"
    name = type(exc).__name__
    if "RateLimit" in name:
        return "rate_limit"
    if "Timeout" in name:
        return "timeout"
    if any(s in name for s in ("ServerError", "InternalServer", "ServiceUnavailable", "BadGateway")):
        return "server_error"
    if "Connection" in name:
        return "network_error"
    if any(s in name for s in ("BadRequest", "Authentication", "Permission", "NotFound", "Conflict", "UnprocessableEntity")):
        return "client_error"
    return "other_error"
