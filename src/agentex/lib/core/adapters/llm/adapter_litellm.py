from typing import override
from collections.abc import Generator, AsyncGenerator

import litellm as llm

from agentex.lib.utils.logging import make_logger
from agentex.lib.types.llm_messages import Completion
from agentex.lib.core.adapters.llm.port import LLMGateway

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

        # Return a single completion for non-streaming
        response = await llm.acompletion(*args, **kwargs)
        return Completion.model_validate(response)

    @override
    async def acompletion_stream(
        self, *args, **kwargs
    ) -> AsyncGenerator[Completion, None]:
        if not kwargs.get("stream"):
            raise ValueError("To use streaming, please set stream=True in the kwargs")

        async for chunk in await llm.acompletion(*args, **kwargs):  # type: ignore[misc]
            yield Completion.model_validate(chunk)
