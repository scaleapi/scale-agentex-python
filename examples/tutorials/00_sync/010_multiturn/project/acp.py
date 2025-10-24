import os
from typing import Union, AsyncGenerator

from agentex.lib import adk
from agentex.lib.types.acp import SendMessageParams
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.types.llm_messages import LLMConfig, UserMessage, SystemMessage, AssistantMessage
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.types.task_message_update import TaskMessageUpdate
from agentex.types.task_message_content import TaskMessageContent
from agentex.types import TextContent

# Create an ACP server
acp = FastACP.create(
    acp_type="sync",
)


class StateModel(BaseModel):
    system_prompt: str
    model: str


# Note: The return of this handler is required to be persisted by the Agentex Server
@acp.on_message_send
async def handle_message_send(
    params: SendMessageParams,
) -> Union[TaskMessageContent, AsyncGenerator[TaskMessageUpdate, None]]:
    """
    In this tutorial, we'll see how to handle a basic multi-turn conversation without streaming.
    """
    #########################################################
    # 0. Validate the message.
    #########################################################

    if not hasattr(params.content, "type") or params.content.type != "text":
        raise ValueError(f"Expected text message, got {getattr(params.content, 'type', 'unknown')}")

    if not hasattr(params.content, "author") or params.content.author != "user":
        raise ValueError(f"Expected user message, got {getattr(params.content, 'author', 'unknown')}")

    if not os.environ.get("OPENAI_API_KEY"):
        return TextContent(
            author="agent",
            content="Hey, sorry I'm unable to respond to your message because you're running this example without an OpenAI API key. Please set the OPENAI_API_KEY environment variable to run this example. Do this by either by adding a .env file to the project/ directory or by setting the environment variable in your terminal.",
        )

    #########################################################
    # 1. Initialize the state. Using state is optional, but it's a good way to store information between turns.
    #########################################################

    # Try to retrieve the state. If it doesn't exist, create it.
    task_state = await adk.state.get_by_task_and_agent(task_id=params.task.id, agent_id=params.agent.id)

    if not task_state:
        # If the state doesn't exist, create it.
        state = StateModel(system_prompt="You are a helpful assistant that can answer questions.", model="gpt-4o-mini")
        task_state = await adk.state.create(task_id=params.task.id, agent_id=params.agent.id, state=state)
    else:
        state = StateModel.model_validate(task_state.state)

    #########################################################
    # 2. Fetch our message history.
    #########################################################

    task_messages = await adk.messages.list(task_id=params.task.id)

    #########################################################
    # 3. Convert task messages to LLM messages.
    #########################################################

    # This might seem duplicative, but the split between TaskMessage and LLMMessage is intentional and important.

    llm_messages = [
        SystemMessage(content=state.system_prompt),
        *[
            UserMessage(content=getattr(message.content, "content", ""))
            if getattr(message.content, "author", None) == "user"
            else AssistantMessage(content=getattr(message.content, "content", ""))
            for message in task_messages
            if getattr(message.content, "type", None) == "text"
        ],
    ]

    # TaskMessages are messages that are sent between an Agent and a Client. They are fundamentally decoupled from messages sent to the LLM. This is because you may want to send additional metadata to allow the client to render the message on the UI differently.

    # LLMMessages are OpenAI-compatible messages that are sent to the LLM, and are used to track the state of a conversation with a model.

    # In simple scenarios your conversion logic will just look like this. However, in complex scenarios where you are leveraging the flexibility of the TaskMessage type to send non-LLM-specific metadata, you should write custom conversion logic.

    # Some complex scenarios include:
    #   - Taking a markdown document output by an LLM, postprocessing it into a JSON object to clearly denote title, content, and footers. This can be sent as a DataContent TaskMessage to the client and converted back to markdown here to send back to the LLM.
    #   - If using multiple LLMs (like in an actor-critic framework), you may want to send DataContent that denotes which LLM generated which part of the output and write conversion logic to split the TaskMessagehistory into multiple LLM conversations.
    #   - If using multiple LLMs, but one LLM's output should not be sent to the user (i.e. a critic model), you can leverage the State as an internal storage mechanism to store the critic model's conversation history. This i s a powerful and flexible way to handle complex scenarios.

    #########################################################
    # 4. Call an LLM to respond to the user's message.
    #########################################################

    # Call an LLM to respond to the user's message
    chat_completion = await adk.providers.litellm.chat_completion(
        llm_config=LLMConfig(model=state.model, messages=llm_messages),
        trace_id=params.task.id,
    )

    #########################################################
    # 5. Return the agent response to the client.
    #########################################################

    # The Agentex server automatically commits input and output messages to the database so you don't need to do this yourself, simply process the input content and return the output content.

    # Return the agent response to the client
    if chat_completion.choices[0].message:
        content_str = chat_completion.choices[0].message.content or ""
    else:
        content_str = ""

    return TextContent(author="agent", content=content_str)
