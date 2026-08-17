from typing import Any, override
from collections.abc import Mapping, Generator, AsyncGenerator

import litellm as llm
from sgp_obs.traces import instrument_stream, instrument_stream_sync

from agentex.lib.utils.logging import make_logger
from agentex.lib.types.llm_messages import Completion
from agentex.lib.core.adapters.llm.port import LLMGateway

logger = make_logger(__name__)


def _delta_content(chunk: Completion) -> Any:
    """Text delta of a streaming chunk, or ``None`` — defensive against provider shape.
    Obs extractors must never raise into the stream."""
    try:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            return None
        delta = getattr(choices[0], "delta", None)
        return getattr(delta, "content", None) if delta is not None else None
    except Exception:
        return None


def _output_tokens(chunk: Completion) -> int:
    # 1 per content-bearing delta — a good streaming proxy without a tokenizer.
    return 1 if _delta_content(chunk) else 0


def _is_answer(chunk: Completion) -> bool:
    # First user-visible answer token (text); skips role-only / tool-call / empty deltas.
    return bool(_delta_content(chunk))


def _stream_attrs(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Mapping[str, Any]:
    model = kwargs.get("model") or (args[0] if args else None)
    attrs: dict[str, Any] = {"gen_ai.system": "litellm", "gen_ai.operation.name": "chat"}
    if model:
        attrs["gen_ai.request.model"] = str(model)
    return attrs


class LiteLLMGateway(LLMGateway):
    @override
    def completion(self, *args, **kwargs) -> Completion:
        if kwargs.get("stream", True):
            raise ValueError(
                "Please use self.completion_stream instead of self.completion to stream responses"
            )

        response = llm.completion(*args, **kwargs)
        return Completion.model_validate(response)

    @override
    def completion_stream(self, *args, **kwargs) -> Generator[Completion, None, None]:
        if not kwargs.get("stream"):
            raise ValueError("To use streaming, please set stream=True in the kwargs")

        def _chunks() -> Generator[Completion, None, None]:
            for chunk in llm.completion(*args, **kwargs):
                yield Completion.model_validate(chunk)

        # Wrap the whole generation in one gen_ai.chat span (TTFT/TTAT events +
        # decode-window tps/tpot/output-tokens). Fail-open; chunks pass through.
        yield from instrument_stream_sync(
            _chunks(),
            name="gen_ai.chat",
            attributes=_stream_attrs(args, kwargs),
            output_tokens=_output_tokens,
            is_answer=_is_answer,
        )

    @override
    async def acompletion(self, *args, **kwargs) -> Completion:
        if kwargs.get("stream", True):
            raise ValueError(
                "Please use self.acompletion_stream instead of self.acompletion to stream responses"
            )

        # Return a single completion for non-streaming
        response = await llm.acompletion(*args, **kwargs)
        return Completion.model_validate(response)

    @override
    async def acompletion_stream(
        self, *args, **kwargs
    ) -> AsyncGenerator[Completion, None]:
        if not kwargs.get("stream"):
            raise ValueError("To use streaming, please set stream=True in the kwargs")

        async def _chunks() -> AsyncGenerator[Completion, None]:
            async for chunk in await llm.acompletion(*args, **kwargs):  # type: ignore[misc]
                yield Completion.model_validate(chunk)

        async for completion in instrument_stream(
            _chunks(),
            name="gen_ai.chat",
            attributes=_stream_attrs(args, kwargs),
            output_tokens=_output_tokens,
            is_answer=_is_answer,
        ):
            yield completion
