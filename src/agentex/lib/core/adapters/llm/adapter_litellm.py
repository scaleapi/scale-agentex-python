from typing import override
from collections.abc import Generator, AsyncGenerator

import litellm as llm

from agentex.lib.utils.logging import make_logger
from agentex.lib.types.llm_messages import Completion
from agentex.lib.core.adapters.llm.port import LLMGateway
from agentex.lib.core.adapters.llm._genai_metrics import inference_call

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

        for chunk in llm.completion(*args, **kwargs):
            yield Completion.model_validate(chunk)

    @override
    async def acompletion(self, *args, **kwargs) -> Completion:
        if kwargs.get("stream", True):
            raise ValueError(
                "Please use self.acompletion_stream instead of self.acompletion to stream responses"
            )

        # `async with`, not try/except: asyncio.CancelledError is a BaseException, so a
        # caller that disappears mid-flight would skip an `except Exception` handler and
        # the record would be silently dropped.
        async with inference_call(kwargs) as call:
            # Return a single completion for non-streaming
            response = call.observe(await llm.acompletion(*args, **kwargs))
            return Completion.model_validate(response)

    @override
    async def acompletion_stream(
        self, *args, **kwargs
    ) -> AsyncGenerator[Completion, None]:
        if not kwargs.get("stream"):
            raise ValueError("To use streaming, please set stream=True in the kwargs")

        async with inference_call(kwargs) as call:
            # observe() takes ownership of the stream and yields the same chunks, so it
            # can read time-to-first-chunk and the token totals off the last chunk.
            # Wrapping only the `await` would return before the first chunk arrived and
            # record zero tokens for every streamed call.
            stream = call.observe(await llm.acompletion(*args, **kwargs))
            async for chunk in stream:  # type: ignore[misc]
                yield Completion.model_validate(chunk)
