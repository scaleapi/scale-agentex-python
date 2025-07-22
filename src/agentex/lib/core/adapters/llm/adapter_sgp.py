import os
from collections.abc import AsyncGenerator, Generator

from scale_gp import AsyncSGPClient, SGPClient

from agentex.lib.core.adapters.llm.port import LLMGateway
from agentex.lib.types.llm_messages import Completion
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class SGPLLMGateway(LLMGateway):
    def __init__(self, sgp_api_key: str | None = None):
        self.sync_client = SGPClient(api_key=os.environ.get("SGP_API_KEY", sgp_api_key))
        self.async_client = AsyncSGPClient(
            api_key=os.environ.get("SGP_API_KEY", sgp_api_key)
        )

    def completion(self, *args, **kwargs) -> Completion:
        if kwargs.get("stream", True):
            raise ValueError(
                "Please use self.completion_stream instead of self.completion to stream responses"
            )

        response = self.sync_client.beta.chat.completions.create(*args, **kwargs)
        return Completion.model_validate(response)

    def completion_stream(self, *args, **kwargs) -> Generator[Completion, None, None]:
        if not kwargs.get("stream"):
            raise ValueError("To use streaming, please set stream=True in the kwargs")

        for chunk in self.sync_client.beta.chat.completions.create(*args, **kwargs):
            yield Completion.model_validate(chunk)

    async def acompletion(self, *args, **kwargs) -> Completion:
        if kwargs.get("stream", True):
            raise ValueError(
                "Please use self.acompletion_stream instead of self.acompletion to stream responses"
            )

        # Return a single completion for non-streaming
        response = await self.async_client.beta.chat.completions.create(*args, **kwargs)
        return Completion.model_validate(response)

    async def acompletion_stream(
        self, *args, **kwargs
    ) -> AsyncGenerator[Completion, None]:
        if not kwargs.get("stream"):
            raise ValueError("To use streaming, please set stream=True in the kwargs")

        async for chunk in await self.async_client.beta.chat.completions.create(
            *args, **kwargs
        ):
            yield Completion.model_validate(chunk)
