import os
from typing import Union, AsyncGenerator

from agents import Agent, Runner, RunConfig

from agentex.lib import adk
from agentex.lib.types.acp import SendMessageParams
from agentex.lib.types.converters import convert_task_messages_to_oai_agents_inputs
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.types.task_message_update import TaskMessageUpdate, StreamTaskMessageFull
from agentex.types.task_message_content import TextContent, TaskMessageContent
from agentex.lib.adk.providers._modules.sync_provider import (
    SyncStreamingProvider,
    convert_openai_to_agentex_events,
)

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
    # 1-3. These steps are all the same as the hello acp tutorial.
    #########################################################

    if not params.content:
        return

    if not hasattr(params.content, "type") or params.content.type != "text":
        raise ValueError(f"Expected text message, got {getattr(params.content, 'type', 'unknown')}")

    if not hasattr(params.content, "author") or params.content.author != "user":
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


    # Initialize the provider and run config to allow for tracing
    provider = SyncStreamingProvider(
        trace_id=params.task.id,
    )

    # Initialize the run config to allow for tracing and streaming
    run_config = RunConfig(
        model_provider=provider,
    )


    test_agent = Agent(name="assistant", instructions=state.system_prompt, model=state.model)

    # Convert task messages to OpenAI Agents SDK format
    input_list = convert_task_messages_to_oai_agents_inputs(task_messages)

    # Run the agent and stream the events
    result = Runner.run_streamed(test_agent, input_list, run_config=run_config)


    #########################################################
    # 4. Stream the events to the client.
    #########################################################
    # Convert the OpenAI events to Agentex events
    # This is done by converting the OpenAI events to Agentex events and yielding them to the client
    stream = result.stream_events()

    # Yield the Agentex events to the client
    async for agentex_event in convert_openai_to_agentex_events(stream):
        yield agentex_event

