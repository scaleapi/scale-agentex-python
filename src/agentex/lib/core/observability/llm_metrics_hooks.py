"""``RunHooks`` adapter that emits per-call LLM metrics.

Used by the sync ACP path and as a base class for ``TemporalStreamingHooks``
on the async path, so token / request / cache metrics emit consistently
across both. Streaming-only metrics (ttft, ttat, tps) are emitted from the
streaming model itself, not here — hooks don't see individual chunks.
"""

from __future__ import annotations

from typing import Any

from agents import Agent, RunHooks, ModelResponse, RunContextWrapper

from agentex.lib.core.observability.llm_metrics import classify_status, get_llm_metrics


class LLMMetricsHooks(RunHooks):
    """Emits ``agentex.llm.requests`` + token counters on every LLM call."""

    async def on_llm_end(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        response: ModelResponse,
    ) -> None:
        del context  # part of the RunHooks contract; unused here
        m = get_llm_metrics()
        attrs = {"model": str(agent.model) if agent.model else "unknown"}
        # Request counter only depends on agent.model, so emit it first and
        # outside the usage-extraction try block. Token counters reach into
        # nested optional fields and are best-effort: a non-OpenAI provider
        # (litellm-routed Anthropic, etc.) may return a Usage shape missing
        # input_tokens_details / output_tokens_details — we emit zeros where
        # we can and skip the rest rather than crash the caller.
        try:
            m.requests.add(1, {**attrs, "status": "success"})
        except Exception:
            pass
        try:
            usage = response.usage
            m.input_tokens.add(usage.input_tokens or 0, attrs)
            m.output_tokens.add(usage.output_tokens or 0, attrs)
            m.cached_input_tokens.add(usage.input_tokens_details.cached_tokens or 0, attrs)
            m.reasoning_tokens.add(usage.output_tokens_details.reasoning_tokens or 0, attrs)
        except Exception:
            pass


def record_llm_failure(model: str, exc: BaseException) -> None:
    """Best-effort counter bump for an LLM call that raised before ``on_llm_end``."""
    try:
        get_llm_metrics().requests.add(1, {"model": model, "status": classify_status(exc)})
    except Exception:
        pass
