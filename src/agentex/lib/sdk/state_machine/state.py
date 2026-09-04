from pydantic import BaseModel, ConfigDict

from agentex.lib.sdk.state_machine.state_workflow import StateWorkflow


class State(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    workflow: StateWorkflow
