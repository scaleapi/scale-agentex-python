from __future__ import annotations

import os
from typing import override
from collections.abc import Generator, AsyncGenerator

from scale_gp import SGPClient, AsyncSGPClient

from agentex.lib.utils.logging import make_logger
from agentex.lib.types.llm_messages import Completion
from agentex.lib.core.adapters.llm.port import LLMGateway

logger = make_logger(__name__)


class SGPLLMGateway(LLMGateway):
    def __init__(self, sgp_api_key: str | None = None):
        self.sync_client = SGPClient(api_key=os.environ.get("SGP_API_KEY", sgp_api_key))
        self.async_client = AsyncSGPClient(
            api_key=os.environ.get("SGP_API_KEY", sgp_api_key)
        )

    @override
    def completion(self, *args, **kwargs) -> Completion:
        if kwargs.get("stream", True):
            raise ValueError(
                "Please use self.completion_stream instead of self.completion to stream responses"
            )

        response = self.sync_client.beta.chat.completions.create(*args, **kwargs)
        return Completion.model_validate(response)

    @override
    def completion_stream(self, *args, **kwargs) -> Generator[Completion, None, None]:
        if not kwargs.get("stream"):
            raise ValueError("To use streaming, please set stream=True in the kwargs")

        for chunk in self.sync_client.beta.chat.completions.create(*args, **kwargs):
            yield Completion.model_validate(chunk)

    @override
    async def acompletion(self, *args, **kwargs) -> Completion:
        if kwargs.get("stream", True):
            raise ValueError(
                "Please use self.acompletion_stream instead of self.acompletion to stream responses"
            )

        # Return a single completion for non-streaming
        response = await self.async_client.beta.chat.completions.create(*args, **kwargs)
        return Completion.model_validate(response)

    @override
    async def acompletion_stream(
        self, *args, **kwargs
    ) -> AsyncGenerator[Completion, None]:
        if not kwargs.get("stream"):
            raise ValueError("To use streaming, please set stream=True in the kwargs")

        async for chunk in self.async_client.beta.chat.completions.create(*args, **kwargs):  # type: ignore[misc]
            yield Completion.model_validate(chunk)
