from abc import ABC, abstractmethod

from temporalio import workflow

from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.types.acp import CreateTaskParams, SendEventParams
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class BaseWorkflow(ABC):
    def __init__(
        self,
        display_name: str,
    ):
        self.display_name = display_name

    @abstractmethod
    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        raise NotImplementedError

    @abstractmethod
    async def on_task_create(self, params: CreateTaskParams) -> None:
        raise NotImplementedError
