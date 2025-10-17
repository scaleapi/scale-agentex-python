from __future__ import annotations

from typing import TYPE_CHECKING, override

from pydantic import BaseModel

from agentex.lib.utils.logging import make_logger
from agentex.lib.sdk.state_machine.state_workflow import StateWorkflow

if TYPE_CHECKING:
    from agentex.lib.sdk.state_machine import StateMachine

logger = make_logger(__name__)


class NoOpWorkflow(StateWorkflow):
    """
    Workflow that does nothing. This is commonly used as a terminal state.
    """

    @override
    async def execute(
        self, state_machine: "StateMachine", state_machine_data: BaseModel | None = None
    ) -> str:
        return state_machine.get_current_state()  # Stay in current state
