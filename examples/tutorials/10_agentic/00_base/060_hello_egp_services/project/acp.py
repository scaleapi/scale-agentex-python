import os
import json
import logging
from datetime import datetime
from jinja2 import Template
from typing import List, Union

from agentex.lib import adk
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.acp import SendEventParams, CreateTaskParams, CancelTaskParams
from agentex.lib.types.fastacp import AgenticACPConfig
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.types.llm_messages import Message, UserMessage, SystemMessage
from agentex.types.text_content import TextContent
from agentex.types.task_message_content import TaskMessageContent, ToolRequestContent, ToolResponseContent

from egp_services.nodes import ToolGenerationNode, RetrieverNode, ChatGenerationNode
from egp_services.nodes.generation.tool_generation import ToolConfig
from oldowan.completions import ToolMessage, ChatCompletionMessage

logger = logging.getLogger(__name__)

assert os.environ.get("SGP_API_KEY") is not None, "SGP_API_KEY is not set"
assert os.environ.get("SGP_ACCOUNT_ID") is not None, "SGP_ACCOUNT_ID is not set"

# Create an ACP server
acp = FastACP.create(
    acp_type="agentic",
    config=AgenticACPConfig(type="base"),
)



TOOL_GENERATION_NODE = ToolGenerationNode(
    model="openai/gpt-4o",
    tools=[
        ToolConfig(name="nodes.ChatGenerationNode", init_kwargs={'llm_model' : 'anthropic/claude-3-7-sonnet-20250219'}), 
        ToolConfig(name="internal.google_search"),
    ],
    client_kwargs={"api_key": os.environ.get("SGP_API_KEY"), "account_id": os.environ.get("SGP_ACCOUNT_ID")}
)

CHAT_GENERATION_NODE = ChatGenerationNode(
    model="openai/gpt-4o",
    client_kwargs={"api_key": os.environ.get("SGP_API_KEY"), "account_id": os.environ.get("SGP_ACCOUNT_ID")}
)

RETRIEVER_NODE = RetrieverNode(
    knowledge_base_id="bb9095d0-a93a-4353-a9f5-44c54d0060ac",
    client_kwargs={"api_key": os.environ.get("SGP_API_KEY"), "account_id": os.environ.get("SGP_ACCOUNT_ID")}
)

CREATE_RETRIEVAL_QUERY_USER_PROMPT = """
You are a helpful assistant that creates a retrieval query for a knowledge base based on the current state of the conversation.

Here is the current state of the conversation:

{% for message in messages %}
{{ message.role }}: {{ message.content }}
{% endfor %}

Now create a retrieval query for the knowledge base.
"""

TOOL_ENABLED_ASSISTANT_SYSTEM_PROMPT = """
You are a helpful assistant that uses tools to answer questions.

Here is some context for the conversation:

{% for chunk in chunks %}

Chunk ID: {{ chunk.chunk_id }}

{{ chunk.text }}

{% endfor %}

Good luck!
"""

TOOL_RESPONSE_ID_SUFFIX = "_response"

class StateModel(BaseModel):
    turn_number: int # The number of turns the agent has taken
    messages: List[Message] # The messages the agent has seen

# Converts an egp service message to an agentex task message
def convert_message_to_task_message(message: Union[ChatCompletionMessage, ToolMessage]) -> List[TaskMessageContent]:
    task_messages = []
    if isinstance(message, ChatCompletionMessage):
        # Always return the ChatCompletionMessage first 
        if message.content is not None:
                    task_messages.append(TextContent(
            author="agent",
            content=message.content,
        ))
        
        # Then add on the tool calls
        if message.tool_calls is not None:
            for tool_call in message.tool_calls:
                task_messages.append(ToolRequestContent(
                    author="agent",
                    name=tool_call.function.name,
                    arguments=json.loads(tool_call.function.arguments),
                ))
    
    # FInally add the Tool REsponse
    elif isinstance(message, ToolMessage):
        task_messages.append(ToolResponseContent(
            author="agent",
            content=message.content,
            name=message.name,
        ))
    return task_messages


async def handle_turn(task_id: str, state: StateModel, content: str):
    """Shared function for handling a turn in the task"""
    # Echo back the user's initial message
    await adk.messages.create(
        task_id=task_id,
        content=TextContent(
            author="user",
            content=content,
        ),
        trace_id=task_id,
    )

    # Add the user's message to the state
    state.messages.append(UserMessage(content=content))

    # Create a span for the entire turn
    async with adk.tracing.span(
        trace_id=task_id,
        name=f"Turn {state.turn_number}",
        input=state,
    ) as span:
        # 1. Summarize the current state
        retrieval_query_messages = [
            UserMessage(content=Template(CREATE_RETRIEVAL_QUERY_USER_PROMPT).render(messages=state.messages)),
        ]
        async with adk.tracing.span(
            trace_id=task_id,
            name=f"Create Retrieval Query",
            parent_id=span.id,
            input={"retrieval_query_messages": retrieval_query_messages},
        ) as retrieval_query_span:
            retrieval_query = CHAT_GENERATION_NODE(
                messages=retrieval_query_messages,
            )
            retrieval_query_span.end_time = datetime.now()
            retrieval_query_span.output = {"retrieval_query": retrieval_query}

        print(f"Retrieval query about to be sent: {retrieval_query} - class: {type(retrieval_query)} - class name: {type(retrieval_query).__name__}")

        # 2. Do a retrieval function
        async with adk.tracing.span(
            trace_id=task_id,
            name=f"Retrieve Chunks",
            parent_id=span.id,
            input={"retrieval_query": retrieval_query},
        ) as retrieve_chunks_span:
            chunks = RETRIEVER_NODE(query=retrieval_query.output, num_to_return=2)
            retrieve_chunks_span.end_time = datetime.now()
            retrieve_chunks_span.output = {"chunks": chunks}


        # 3. Do a tool enabled generation
        tool_enabled_llm_messages = [
            SystemMessage(content=Template(TOOL_ENABLED_ASSISTANT_SYSTEM_PROMPT).render(chunks=chunks)),
            *state.messages,
        ]
        # Trace the full node
        async with adk.tracing.span(
            trace_id=task_id,
            name=f"Generate Response",
            parent_id=span.id,
            input={"tool_enabled_llm_messages": tool_enabled_llm_messages},
        ) as generate_response_span:
            messages = await TOOL_GENERATION_NODE.async_call(
                messages=tool_enabled_llm_messages,
            )

            # For each message, trace it and send it to the client
            for idx, message in enumerate(messages):
                async with adk.tracing.span(
                    trace_id=task_id,
                    name=f"Message {idx}",
                    parent_id=generate_response_span.id,
                    input={"messages": tool_enabled_llm_messages + messages[:idx]},
                ) as message_span:
                    task_messages = convert_message_to_task_message(message)
                    for task_message in task_messages:
                        await adk.messages.create(
                            task_id=task_id,
                            content=task_message,
                            trace_id=task_id,
                            parent_span_id=message_span.id,
                        )

                    message_span.output = {"message": message}

            generate_response_span.end_time = datetime.now()
            generate_response_span.output = {"messages": messages}

        # Update the task state with the new messages
        state.messages.extend(messages)
        state.turn_number += 1

        span.end_time = datetime.now()

    return state
    

@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    # Upon task creation, we initialize the task state with a system message.
    # This will be fetched by the `on_task_event_send` handler when each event is sent.
    state = StateModel(
        messages=[],
        turn_number=0,
    )
    await adk.state.create(task_id=params.task.id, agent_id=params.agent.id, state=state)


# Note: The return of this handler is required to be persisted by the Agentex Server
@acp.on_task_event_send
async def handle_message_send(params: SendEventParams):
    #########################################################
    # 1-3. These steps are all the same as the hello acp tutorial.
    #########################################################

    if not params.event.content:
        return

    if params.event.content.type != "text":
        raise ValueError(f"Expected text message, got {params.event.content.type}")

    if params.event.content.author != "user":
        raise ValueError(f"Expected user message, got {params.event.content.author}")

    # Try to retrieve the state. If it doesn't exist, create it.
    task_state = await adk.state.get_by_task_and_agent(task_id=params.task.id, agent_id=params.agent.id)
    state = StateModel.model_validate(task_state.state)
    
    #########################################################
    # 4. Call an LLM to respond to the user's message and stream the response to the client.
    #########################################################

    state = await handle_turn(task_id=params.task.id, state=state, content=params.event.content.content)

    # Update the state with the new messages
    await adk.state.update(
        task_id=params.task.id,
        agent_id=params.agent.id,
        state_id=task_state.id,
        state=state,
        trace_id=params.task.id,
    )

@acp.on_task_cancel
async def handle_task_cancel(params: CancelTaskParams):
    """Default task cancel handler"""
    logger.info(f"Task canceled: {params.task}")