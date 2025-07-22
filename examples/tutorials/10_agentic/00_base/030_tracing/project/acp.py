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
    turn_number: int


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    # Upon task creation, we initialize the task state with a system message.
    # This will be fetched by the `on_task_event_send` handler when each event is sent.

    #########################################################
    # 1. Initialize the task state.
    #########################################################

    state = StateModel(
        messages=[SystemMessage(content="You are a helpful assistant that can answer questions.")],
        turn_number=0,
    )
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
    # 3. Retrieve the task state.
    #########################################################

    task_state = await adk.state.get_by_task_and_agent(task_id=params.task.id, agent_id=params.agent.id)
    state = StateModel.model_validate(task_state.state)
    state.turn_number += 1

    # Add the new user message to the message history
    state.messages.append(UserMessage(content=params.event.content.content))

    #########################################################
    # 4. (👋) Create a tracing span.
    #########################################################

    # Create a tracing span. All of the Agentex ADK methods are "auto-traced", but by default show up as a flat list associated with a single trace id (which is usually just set to the task id by default).
    # If you want to create a hierarchical trace, you can do so by creating spans in your business logic and passing the span id to the ADK methods. Traces will be grouped under parent spans for better readability.
    # If you're not trying to create a hierarchical trace, but just trying to create a custom span to trace something, you can use this too to create a custom span that is associate with your trace by trace ID.

    async with adk.tracing.span(
        trace_id=params.task.id,
        name=f"Turn {state.turn_number}",
        input=state
    ) as span:
        
        #########################################################
        # 5. Echo back the user's message so it shows up in the UI.
        #########################################################

        # (👋) Notice that we pass the parent_span_id to the ADK methods to create a hierarchical trace.
        await adk.messages.create(
            task_id=params.task.id,
            trace_id=params.task.id,
            content=params.event.content,
            parent_span_id=span.id if span else None,
        )

        #########################################################
        # 6. If the OpenAI API key is not set, send a message to the user to let them know.
        #########################################################
        
        # (👋) Notice that we pass the parent_span_id to the ADK methods to create a hierarchical trace.
        if not os.environ.get("OPENAI_API_KEY"):
            await adk.messages.create(
                task_id=params.task.id,
                trace_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content="Hey, sorry I'm unable to respond to your message because you're running this example without an OpenAI API key. Please set the OPENAI_API_KEY environment variable to run this example. Do this by either by adding a .env file to the project/ directory or by setting the environment variable in your terminal.",
                ),
                parent_span_id=span.id if span else None,
            )

        #########################################################
        # 7. Call an LLM to respond to the user's message
        #########################################################

        # (👋) Notice that we pass the parent_span_id to the ADK methods to create a hierarchical trace.
        task_message = await adk.providers.litellm.chat_completion_stream_auto_send(
            task_id=params.task.id,
            llm_config=LLMConfig(model="gpt-4o-mini", messages=state.messages, stream=True),
            trace_id=params.task.id,
            parent_span_id=span.id if span else None,
        )
        
        state.messages.append(AssistantMessage(content=task_message.content.content))
        
        #########################################################
        # 8. Store the messages in the task state for the next turn
        #########################################################

        # (👋) Notice that we pass the parent_span_id to the ADK methods to create a hierarchical trace.
        await adk.state.update(
            state_id=task_state.id,
            task_id=params.task.id,
            agent_id=params.agent.id,
            state=state,
            trace_id=params.task.id,
            parent_span_id=span.id if span else None,
        )

        #########################################################
        # 9. (👋) Set the span output to the state for the next turn
        #########################################################

        # (👋) You can store an arbitrary pydantic model or dictionary in the span output. The idea of a span is that it easily allows you to compare the input and output of a span to see what the wrapped function did.
        # In this case, the state is comprehensive and expressive, so we just store the change in state that occured.
        span.output = state

@acp.on_task_cancel
async def handle_task_cancel(params: CancelTaskParams):
    """Default task cancel handler"""
    logger.info(f"Task canceled: {params.task}")
