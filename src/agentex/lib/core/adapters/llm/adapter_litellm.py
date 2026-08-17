from typing import override
from collections.abc import Generator, AsyncGenerator

import litellm as llm
from sgp_obs.traces import instrument_stream, instrument_stream_sync

from agentex.lib.utils.logging import make_logger
from agentex.lib.types.llm_messages import Completion
from agentex.lib.core.adapters.llm.port import LLMGateway
from agentex.lib.core.adapters.llm._stream_obs import is_answer, stream_attrs, output_tokens

logger = make_logger(__name__)


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
            attributes=stream_attrs("litellm", args, kwargs),
            output_tokens=output_tokens,
            is_answer=is_answer,
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
            attributes=stream_attrs("litellm", args, kwargs),
            output_tokens=output_tokens,
            is_answer=is_answer,
        ):
            yield completion
