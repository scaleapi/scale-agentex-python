from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Generator

from agentex.lib.types.llm_messages import Completion


class LLMGateway(ABC):
    @abstractmethod
    def completion(self, *args, **kwargs) -> Completion:
        raise NotImplementedError

    @abstractmethod
    def completion_stream(self, *args, **kwargs) -> Generator[Completion, None, None]:
        raise NotImplementedError

    @abstractmethod
    async def acompletion(self, *args, **kwargs) -> Completion:
        raise NotImplementedError

    @abstractmethod
    async def acompletion_stream(
        self, *args, **kwargs
    ) -> AsyncGenerator[Completion, None]:
        raise NotImplementedError
