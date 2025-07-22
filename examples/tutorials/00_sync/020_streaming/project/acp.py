import os
from typing import AsyncGenerator, Union

from agentex.lib import adk
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.acp import SendMessageParams
from agentex.lib.types.llm_messages import AssistantMessage, LLMConfig, SystemMessage, UserMessage
from agentex.lib.types.task_message_updates import StreamTaskMessageDelta, StreamTaskMessageDone, StreamTaskMessageFull, TaskMessageUpdate, TextDelta
from agentex.lib.utils.model_utils import BaseModel
from agentex.types.task_message_content import TaskMessageContent, TextContent

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

    if params.content.type != "text":
        raise ValueError(f"Expected text message, got {params.content.type}")

    if params.content.author != "user":
        raise ValueError(f"Expected user message, got {params.content.author}")
    
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
            UserMessage(content=message.content.content) if message.content.author == "user" else AssistantMessage(content=message.content.content)
            for message in task_messages
            if message.content and message.content.type == "text"
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
                index=message_index,
                delta=TextDelta(text_delta=chunk.choices[0].delta.content or ""),
            )

    yield StreamTaskMessageDone(
        index=message_index,
    )
