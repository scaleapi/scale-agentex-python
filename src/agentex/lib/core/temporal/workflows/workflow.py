from abc import ABC, abstractmethod

from temporalio import workflow

from agentex.lib.types.acp import SendEventParams, CreateTaskParams
from agentex.lib.utils.logging import make_logger
from agentex.lib.core.temporal.types.workflow import SignalName

logger = make_logger(__name__)


class BaseWorkflow(ABC):
    def __init__(
        self,
        display_name: str,
    ):
        self.display_name = display_name

    @workflow.query(name="get_current_state")
    def get_current_state(self) -> str:
        """Query handler for the current workflow state.

        Returns "unknown" by default. Subclasses should override this
        to return their actual state, enabling external callers to
        detect turn completion.

        Example override for StateMachine-based agents:

            @workflow.query(name="get_current_state")
            def get_current_state(self) -> str:
                return self.state_machine.get_current_state()
        """
        return "unknown"

    @abstractmethod
    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        raise NotImplementedError

    @abstractmethod
    async def on_task_create(self, params: CreateTaskParams) -> None:
        raise NotImplementedError
