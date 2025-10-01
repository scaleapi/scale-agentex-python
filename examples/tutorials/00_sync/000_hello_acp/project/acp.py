from typing import Union, AsyncGenerator

from agentex.lib.types.acp import SendMessageParams
from agentex.lib.utils.logging import make_logger
from agentex.types.task_message import TaskMessageContent
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.types.task_message_update import TaskMessageUpdate
from agentex.types.task_message_content import TextContent

logger = make_logger(__name__)


# Create an ACP server
acp = FastACP.create(
    acp_type="sync",
)


@acp.on_message_send
async def handle_message_send(
    params: SendMessageParams
) -> Union[TaskMessageContent, AsyncGenerator[TaskMessageUpdate, None]]:
    """Default message handler with streaming support"""
    # Extract content safely from the message
    message_text = ""
    if hasattr(params.content, 'content'):
        content_val = getattr(params.content, 'content', '')
        if isinstance(content_val, str):
            message_text = content_val

    return TextContent(
        author="agent",
        content=f"Hello! I've received your message. Here's a generic response, but in future tutorials we'll see how you can get me to intelligently respond to your message. This is what I heard you say: {message_text}",
    )

