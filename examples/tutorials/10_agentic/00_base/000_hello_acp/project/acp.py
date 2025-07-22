import json
from agentex.lib import adk
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.fastacp import AgenticACPConfig
from agentex.lib.types.acp import CancelTaskParams, CreateTaskParams, SendEventParams

from agentex.types.text_content import TextContent
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


# Create an ACP server with base configuration
# This sets up the core server that will handle task creation, events, and cancellation
acp = FastACP.create(
    acp_type="agentic",
    config=AgenticACPConfig(
        type="base",
    ),
)

@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    # This handler is called first whenever a new task is created.
    # It's a good place to initialize any state or resources needed for the task.

    #########################################################
    # 1. (👋) Do task initialization here.
    #########################################################

    # Acknowledge that the task has been created.
    await adk.messages.create(
        task_id=params.task.id,
        content=TextContent(
            author="agent",
            content=f"Hello! I've received your task. Normally you can do some state initialization here, or just pass and do nothing until you get your first event. For now I'm just acknowledging that I've received a task with the following params:\n\n{json.dumps(params.params, indent=2)}.\n\nYou should only see this message once, when the task is created. All subsequent events will be handled by the `on_task_event_send` handler.",
        ),
    )

@acp.on_task_event_send
async def handle_event_send(params: SendEventParams):
    # This handler is called whenever a new event (like a message) is sent to the task
    
    #########################################################
    # 2. (👋) Echo back the client's message to show it in the UI.
    #########################################################
    
    # This is not done by default so the agent developer has full control over what is shown to the user.
    if params.event.content:
        await adk.messages.create(task_id=params.task.id, content=params.event.content)

    #########################################################
    # 3. (👋) Send a simple response message.
    #########################################################

    # In future tutorials, this is where we'll add more sophisticated response logic.
    await adk.messages.create(
        task_id=params.task.id,
        content=TextContent(
            author="agent",
            content=f"Hello! I've received your message. I can't respond right now, but in future tutorials we'll see how you can get me to intelligently respond to your message.",
        ),
    )

@acp.on_task_cancel
async def handle_task_cancel(params: CancelTaskParams):
    # This handler is called when a task is cancelled.
    # It's useful for cleaning up any resources or state associated with the task.

    #########################################################
    # 4. (👋) Do task cleanup here.
    #########################################################

    # This is mostly for durable workflows that are cancellable like Temporal, but we will leave it here for demonstration purposes.
    logger.info(f"Hello! I've received task cancel for task {params.task.id}: {params.task}. This isn't necessary for this example, but it's good to know that it's available.")
