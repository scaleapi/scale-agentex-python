import os
from typing import Union, AsyncGenerator

from agentex.lib import adk
from agentex.lib.types.acp import SendMessageParams
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.types.llm_messages import LLMConfig, UserMessage, SystemMessage, AssistantMessage
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    TaskMessageUpdate,
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
)
from agentex.types.task_message_content import TextContent, TaskMessageContent

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
    params: SendMessageParams
) -> Union[TaskMessageContent, AsyncGenerator[TaskMessageUpdate, None]]:
    """
    In this tutorial, we'll see how to handle a basic multi-turn conversation without streaming.
    """
    #########################################################
    # 1-3. These steps are all the same as the hello acp tutorial.
    #########################################################

    if not params.content:
        return

    if not hasattr(params.content, 'type') or params.content.type != "text":
        raise ValueError(f"Expected text message, got {getattr(params.content, 'type', 'unknown')}")

    if not hasattr(params.content, 'author') or params.content.author != "user":
        raise ValueError(f"Expected user message, got {getattr(params.content, 'author', 'unknown')}")
    
    if not os.environ.get("OPENAI_API_KEY"):
        yield StreamTaskMessageFull(
            index=0,
            type="full",
            content=TextContent(
                author="agent",
                content="Hey, sorry I'm unable to respond to your message because you're running this example without an OpenAI API key. Please set the OPENAI_API_KEY environment variable to run this example. Do this by either by adding a .env file to the project/ directory or by setting the environment variable in your terminal.",
            ),
        )

    # Try to retrieve the state. If it doesn't exist, create it.
    task_state = await adk.state.get_by_task_and_agent(task_id=params.task.id, agent_id=params.agent.id)

    if not task_state:
        # If the state doesn't exist, create it.
        state = StateModel(system_prompt="You are a helpful assistant that can answer questions.", model="gpt-4o-mini")
        task_state = await adk.state.create(task_id=params.task.id, agent_id=params.agent.id, state=state)
    else:
        state = StateModel.model_validate(task_state.state)

    task_messages = await adk.messages.list(task_id=params.task.id)

    llm_messages = [
        SystemMessage(content=state.system_prompt),
        *[
            UserMessage(content=getattr(message.content, 'content', '')) if getattr(message.content, 'author', None) == "user" else AssistantMessage(content=getattr(message.content, 'content', ''))
            for message in task_messages
            if message.content and getattr(message.content, 'type', None) == "text"
        ]
    ]
    
    #########################################################
    # 4. Call an LLM to respond to the user's message and stream the response to the client.
    #########################################################

    # Call an LLM to respond to the user's message

    print(f"Calling LLM with model {state.model} and messages {llm_messages}")

    # The Agentex server automatically commits input and output messages to the database so you don't need to do this yourself, simply process the input content and return the output content.

    message_index = 0
    async for chunk in adk.providers.litellm.chat_completion_stream(
        llm_config=LLMConfig(model=state.model, messages=llm_messages, stream=True),
        trace_id=params.task.id,
    ):
        if chunk and chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield StreamTaskMessageDelta(
                type="delta",
                index=message_index,
                delta=TextDelta(type="text", text_delta=chunk.choices[0].delta.content or ""),
            )

    yield StreamTaskMessageDone(
        type="done",
        index=message_index,
    )
