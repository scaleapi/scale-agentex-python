from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel

# Import StateMachine only for type checking to avoid circular imports
if TYPE_CHECKING:
    from agentex.lib.sdk.state_machine import StateMachine


class StateWorkflow(ABC):
    @abstractmethod
    async def execute(
        self, state_machine: "StateMachine", state_machine_data: BaseModel | None = None
    ) -> str:
        pass
