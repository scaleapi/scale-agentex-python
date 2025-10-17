from typing import Union, AsyncGenerator

from agentex.lib.types.acp import SendMessageParams, SendEventParams
from agentex.lib.utils.logging import make_logger
from agentex.types.task_message import TaskMessageContent
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.types.task_message_update import TaskMessageUpdate
from agentex.types.task_message_content import TextContent

logger = make_logger(__name__)


# Create an ACP server (agentic type to support event/send)
from agentex.lib.types.fastacp import AgenticACPConfig

acp = FastACP.create(
    acp_type="agentic",
    config=AgenticACPConfig(type="base"),
)


@acp.on_message_send
async def handle_message_send(
    params: SendMessageParams
) -> Union[TaskMessageContent, AsyncGenerator[TaskMessageUpdate, None]]:
    """Message handler - simple echo response"""
    message_text = ""
    if hasattr(params.content, 'content'):
        content_val = getattr(params.content, 'content', '')
        if isinstance(content_val, str):
            message_text = content_val

    return TextContent(
        author="agent",
        content=f"Message received: {message_text}",
    )


@acp.on_task_event_send
async def handle_event_send(params: SendEventParams) -> None:
    """Event handler that validates header forwarding"""
    logger.info(f"=== EVENT RECEIVED ===")
    logger.info(f"Event ID: {params.event.id}")
    logger.info(f"Task ID: {params.task.id}")
    logger.info(f"Agent ID: {params.agent.id}")

    # Check if request headers were forwarded
    if params.request:
        logger.info(f"✅ Request headers present!")
        logger.info(f"Headers: {params.request}")

        # Headers are nested in params.request['headers']
        headers = params.request.get('headers', {})

        # Look for specific test headers
        if 'x-test-auth-key' in headers:
            logger.info(f"✅ Found x-test-auth-key: {headers['x-test-auth-key']}")
        else:
            logger.warning("⚠️  x-test-auth-key not found in request headers")

        if 'x-custom-header' in headers:
            logger.info(f"✅ Found x-custom-header: {headers['x-custom-header']}")
        else:
            logger.warning("⚠️  x-custom-header not found in request headers")
    else:
        logger.error("❌ No request headers forwarded!")

    logger.info(f"=== END EVENT ===")
