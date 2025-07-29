from typing import AsyncGenerator, Union
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.acp import SendMessageParams


from agentex.lib.types.task_message_updates import TaskMessageUpdate
from agentex.types.task_message import TaskMessageContent
from agentex.types.task_message_content import TextContent
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel

logger = make_logger(__name__)


# Create an ACP server
acp = FastACP.create(
    acp_type="sync",
)


class StateModel(BaseModel):
    system_prompt: str
    model: str

@acp.on_message_send
async def handle_message_send(
    params: SendMessageParams
) -> Union[TaskMessageContent, AsyncGenerator[TaskMessageUpdate, None]]:
    from agentex.lib import adk
    """Default message handler with streaming support"""
    # Try to retrieve the state. If it doesn't exist, create it.
    task_state = await adk.state.get_by_task_and_agent(task_id=params.task.id, agent_id=params.agent.id)

    if not task_state:
        # If the state doesn't exist, create it.
        state = StateModel(system_prompt="You are a helpful assistant that can answer questions.", model="gpt-4o-mini")
        task_state = await adk.state.create(task_id=params.task.id, agent_id=params.agent.id, state=state)
    else:
        state = StateModel.model_validate(task_state.state)
    return TextContent(
        author="agent",
        content=f"Hello! I've received your message. Here's a generic response, but in future tutorials we'll see how you can get me to intelligently respond to your message. This is what I heard you say: {params.content.content}",
    )

