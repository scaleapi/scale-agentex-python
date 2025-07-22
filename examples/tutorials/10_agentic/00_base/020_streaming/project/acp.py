import os
from typing import List

from agentex.lib import adk
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.acp import CancelTaskParams, CreateTaskParams, SendEventParams
from agentex.lib.types.fastacp import AgenticACPConfig
from agentex.lib.types.llm_messages import AssistantMessage, LLMConfig, Message, SystemMessage, UserMessage
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel
from agentex.types.text_content import TextContent

logger = make_logger(__name__)


# Create an ACP server

# !!! Warning: Because "Agentic" ACPs are designed to be fully asynchronous, race conditions can occur if parallel events are sent. It is highly recommended to use the "temporal" type in the AgenticACPConfig instead to handle complex use cases. The "base" ACP is only designed to be used for simple use cases and for learning purposes.
acp = FastACP.create(
    acp_type="agentic",
    config=AgenticACPConfig(type="base"),
)

class StateModel(BaseModel):
    messages: List[Message]


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    # Upon task creation, we initialize the task state with a system message.
    # This will be fetched by the `on_task_event_send` handler when each event is sent.

    #########################################################
    # 1. Initialize the task state.
    #########################################################

    state = StateModel(messages=[SystemMessage(content="You are a helpful assistant that can answer questions.")])
    await adk.state.create(task_id=params.task.id, agent_id=params.agent.id, state=state)

@acp.on_task_event_send
async def handle_event_send(params: SendEventParams):
    # !!! Warning: Because "Agentic" ACPs are designed to be fully asynchronous, race conditions can occur if parallel events are sent. It is highly recommended to use the "temporal" type in the AgenticACPConfig instead to handle complex use cases. The "base" ACP is only designed to be used for simple use cases and for learning purposes.

    #########################################################
    # 2. Validate the event content. 
    #########################################################
    if not params.event.content:
        return

    if params.event.content.type != "text":
        raise ValueError(f"Expected text message, got {params.event.content.type}")

    if params.event.content.author != "user":
        raise ValueError(f"Expected user message, got {params.event.content.author}")

    #########################################################
    # 3. Echo back the user's message.
    #########################################################

    await adk.messages.create(
        task_id=params.task.id,
        trace_id=params.task.id,
        content=params.event.content,
    )

    #########################################################
    # 4. If the OpenAI API key is not set, send a message to the user to let them know.
    #########################################################

    if not os.environ.get("OPENAI_API_KEY"):
        await adk.messages.create(
            task_id=params.task.id,
            trace_id=params.task.id,
            content=TextContent(
                author="agent",
                content="Hey, sorry I'm unable to respond to your message because you're running this example without an OpenAI API key. Please set the OPENAI_API_KEY environment variable to run this example. Do this by either by adding a .env file to the project/ directory or by setting the environment variable in your terminal.",
            ),
        )

    #########################################################
    # 5. Retrieve the task state.
    #########################################################

    task_state = await adk.state.get_by_task_and_agent(task_id=params.task.id, agent_id=params.agent.id)
    state = StateModel.model_validate(task_state.state)

    #########################################################
    # 6. Add the new user message to the message history
    #########################################################

    state.messages.append(UserMessage(content=params.event.content.content))

    #########################################################
    # 7. (👋) Call an LLM to respond to the user's message
    #########################################################

    # When we use the streaming version of chat completion, we can either use the `chat_completion_stream_auto_send` method, or we can use the `chat_completion_stream` method. Here is the difference:

    # `chat_completion_stream_auto_send` - This is the "managed version" of the streaming method. It will automatically send the response to the client as an agent TaskMessage.

    # `chat_completion_stream` - This is the "unmanaged version" of the streaming method. It will return a generator of chat completion chunks. You can then do whatever you want with the chunks, such as sending them to the client as an agent message, or storing them in the task state, or whatever you want.

    # Here we use the `chat_completion_stream_auto_send` method.
    #########################################################

    task_message = await adk.providers.litellm.chat_completion_stream_auto_send(
        task_id=params.task.id,
        llm_config=LLMConfig(model="gpt-4o-mini", messages=state.messages, stream=True),
        trace_id=params.task.id,
    )
    
    state.messages.append(AssistantMessage(content=task_message.content.content))

    #########################################################
    # 8. Store the messages in the task state for the next turn
    #########################################################

    await adk.state.update(
        state_id=task_state.id,
        task_id=params.task.id,
        agent_id=params.agent.id,
        state=state,
        trace_id=params.task.id,
    )

@acp.on_task_cancel
async def handle_task_cancel(params: CancelTaskParams):
    """Default task cancel handler"""
    logger.info(f"Task canceled: {params.task}")

