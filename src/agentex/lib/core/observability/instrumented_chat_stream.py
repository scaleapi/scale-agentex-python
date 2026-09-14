"""Async-generator wrapper that instruments a ChatCompletions stream with OTel metrics.

Agents using LiteLLM's ``acompletion(stream=True)`` paired with the
openai-agents-sdk ``ChatCmplStreamHandler`` can wrap their stream with
:func:`instrumented_chat_stream` to get TTFT, TTAT, TPS, cached-token,
and reasoning-token metrics automatically — no per-agent boilerplate.

Usage::

    from agentex.lib.core.observability.instrumented_chat_stream import instrumented_chat_stream

    stream = await litellm.acompletion(**kwargs, stream=True)
    response = Response(...)  # placeholder for ChatCmplStreamHandler
    async for event in instrumented_chat_stream(stream, response, model_name):
        yield event
"""

from __future__ import annotations

import time
import logging
from typing import Any
from collections.abc import AsyncIterator

from agents.items import TResponseStreamEvent
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseTextDeltaEvent,
    ResponseReasoningTextDeltaEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
)
from agents.models.chatcmpl_stream_handler import ChatCmplStreamHandler

from agentex.lib.core.observability.llm_metrics import get_llm_metrics
from agentex.lib.core.observability.llm_metrics_hooks import record_llm_failure

logger = logging.getLogger(__name__)

# Event types that produce tokens (for first_token_at / last_token_at).
_TOKEN_EVENTS = (
    ResponseTextDeltaEvent,
    ResponseReasoningTextDeltaEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
)

# Event types that produce *answer* tokens — excludes reasoning (for first_answer_at).
_ANSWER_EVENTS = (
    ResponseTextDeltaEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
)


async def instrumented_chat_stream(
    raw_stream: AsyncIterator,
    response: Response,
    model_name: str,
) -> AsyncIterator[TResponseStreamEvent]:
    """Wrap a LiteLLM ChatCompletions stream with OTel metrics instrumentation.

    Yields every ``TResponseStreamEvent`` unchanged while recording:

    * ``agentex.llm.ttft`` — time to first content token (ms)
    * ``agentex.llm.ttat`` — time to first answering token, excludes reasoning (ms)
    * ``agentex.llm.tps``  — output tokens / second over the generation window
    * ``agentex.llm.cached_input_tokens`` — prompt-cache hits
    * ``agentex.llm.reasoning_tokens``    — reasoning output tokens

    On exception the ``agentex.llm.requests`` failure counter is bumped via
    :func:`record_llm_failure`.

    Parameters
    ----------
    raw_stream:
        The async iterator returned by ``litellm.acompletion(stream=True)``.
    response:
        A placeholder ``Response`` object required by ``ChatCmplStreamHandler``.
    model_name:
        Model identifier used as the ``model`` metric attribute.
    """
    # --- Usage capture wrapper ---------------------------------------------------
    # LiteLLM's CustomStreamWrapper strips prompt_tokens_details and
    # completion_tokens_details from outgoing chunks.  After the stream ends,
    # stream_chunk_builder() reconstructs the full Usage and writes it back
    # into the *same* _hidden_params dict (shared by reference).  We capture
    # both the raw per-chunk usage and the _hidden_params reference so we can
    # read the complete Usage after iteration.
    raw_usage: Any = None
    _last_hidden_params: dict[str, Any] | None = None

    async def _usage_capturing_stream():  # type: ignore[return]
        nonlocal raw_usage, _last_hidden_params
        async for chunk in raw_stream:
            if hasattr(chunk, "usage") and chunk.usage is not None:
                raw_usage = chunk.usage
            hp = getattr(chunk, "_hidden_params", None)
            if isinstance(hp, dict):
                _last_hidden_params = hp
            yield chunk

    # --- Timing bookmarks --------------------------------------------------------
    stream_start = time.perf_counter()
    first_token_at: float | None = None
    first_answer_at: float | None = None
    last_token_at: float | None = None
    output_tokens_count = 0

    try:
        async for event in ChatCmplStreamHandler.handle_stream(response, _usage_capturing_stream()):
            if isinstance(event, _TOKEN_EVENTS):
                now = time.perf_counter()
                if first_token_at is None:
                    first_token_at = now
                if first_answer_at is None and isinstance(event, _ANSWER_EVENTS):
                    first_answer_at = now
                last_token_at = now
            elif isinstance(event, ResponseCompletedEvent):
                try:
                    if event.response and event.response.usage:
                        output_tokens_count = event.response.usage.output_tokens or 0
                except Exception:
                    pass
            yield event
    except Exception as exc:
        record_llm_failure(model_name, exc)
        raise
    finally:
        try:
            m = get_llm_metrics()
            attrs = {"model": model_name}

            # --- Timing metrics --------------------------------------------------
            if first_token_at is not None:
                m.ttft_ms.record((first_token_at - stream_start) * 1000, attrs)
            if first_answer_at is not None:
                m.ttat_ms.record((first_answer_at - stream_start) * 1000, attrs)
            if (
                first_token_at is not None
                and last_token_at is not None
                and last_token_at > first_token_at
                and output_tokens_count > 0
            ):
                m.tps.record(output_tokens_count / (last_token_at - first_token_at), attrs)

            # --- Token detail counters -------------------------------------------
            # Prefer _hidden_params["usage"] (reconstructed by stream_chunk_builder
            # with all detail fields) over raw per-chunk usage.
            if _last_hidden_params is not None:
                hp_usage = _last_hidden_params.get("usage")
                if hp_usage is not None:
                    raw_usage = hp_usage

            cached_tokens = 0
            reasoning_tokens = 0
            if raw_usage is not None:
                # prompt_tokens_details.cached_tokens (standard OpenAI field)
                ptd = getattr(raw_usage, "prompt_tokens_details", None)
                if ptd is not None:
                    cached_tokens = getattr(ptd, "cached_tokens", 0) or 0
                # Fallback: LiteLLM PrivateAttr _cache_read_input_tokens
                if not cached_tokens:
                    cached_tokens = getattr(raw_usage, "_cache_read_input_tokens", 0) or 0

                ctd = getattr(raw_usage, "completion_tokens_details", None)
                if ctd is not None:
                    reasoning_tokens = getattr(ctd, "reasoning_tokens", 0) or 0

            if cached_tokens > 0:
                m.cached_input_tokens.add(cached_tokens, attrs)
            if reasoning_tokens > 0:
                m.reasoning_tokens.add(reasoning_tokens, attrs)
        except Exception:
            pass
