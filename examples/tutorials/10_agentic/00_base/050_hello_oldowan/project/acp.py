import os
import json
from typing import Callable, List, Union, Dict
from functools import partial
import logging

logger = logging.getLogger(__name__)

from agentex.lib import adk
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.acp import SendEventParams, CreateTaskParams, CancelTaskParams
from agentex.lib.types.fastacp import AgenticACPConfig
from agentex.lib.types.task_message_updates import StreamTaskMessageDelta, StreamTaskMessageFull, TaskMessageUpdate
from agentex.lib.types.task_message_updates import DeltaType, TextDelta, ToolResponseDelta
from agentex.lib.core.services.adk.streaming import StreamingTaskMessageContext
from agentex.lib.utils.model_utils import BaseModel
from agentex.types.span import Span
from agentex.lib.types.llm_messages import Message, UserMessage
from agentex.types.text_content import TextContent
from agentex.types.task_message_content import TaskMessageContent, ToolRequestContent, ToolResponseContent

from oldowan.tools.internal import google_search
from oldowan.completions import ToolMessage, ChatCompletionMessage, simple_agent_acompletion, ChoiceDelta

assert os.environ.get("SGP_API_KEY") is not None, "SGP_API_KEY is not set"
assert os.environ.get("SGP_ACCOUNT_ID") is not None, "SGP_ACCOUNT_ID is not set"

def think(thinking_str: str):
    """
    Use the tool to think about something. It will not obtain new information or change the database, but just append the thought to the log. Use it when complex reasoning or some cache memory is needed.
    Args:
        thinking_str: A thought to think about.
    """
    return 

TOOL_DICT = {
    "google_search": google_search,
    "think": think,
}

# Create an ACP server
acp = FastACP.create(
    acp_type="agentic",
    config=AgenticACPConfig(type="base"),
)

TOOL_RESPONSE_ID_SUFFIX = "_response"

class SimpleAgentCompletionConfig(BaseModel):
    model: str
    tools: List[str]
    max_tokens: int
    stream: bool

class StateModel(BaseModel):
    turn_number: int # The number of turns the agent has taken
    messages: List[Message] # The messages the agent has seen
    simple_agent_completion_config: SimpleAgentCompletionConfig # The function to call to get an agent response

def convert_choice_delta_to_stream_task_message_deltas(choice_delta: ChoiceDelta, parent_task_message: TaskMessage) -> List[StreamTaskMessageDelta]:
    """
    This function converts a ChoiceDelta to a list of StreamTaskMessageDelta objects.
    Args:
        choice_delta: The ChoiceDelta to convert.
        parent_task_message: The parent task message.
    Returns:
        A list of StreamTaskMessageDelta objects.
    """
    # these are tool requests 
    deltas = []
    if choice_delta.tool_calls is not None and choice_delta.tool_calls[0].function.name is not None:
        
        for tool_call in choice_delta.tool_calls:
            # print(tool_call)
            # don't stream tool calls yet.
            # deltas.append(StreamTaskMessageDelta(
            #     index=idx,
            #     content_type=TaskMessageContentType.TOOL_REQUEST,
            #     delta='', # tool_call.function.arguments
            # ))
            pass
    # These are tool responses
    elif choice_delta.role == "tool":
        deltas.append(StreamTaskMessageDelta(
            parent_task_message=parent_task_message,
            delta=ToolResponseDelta(
                type=DeltaType.TOOL_RESPONSE,
                tool_call_id=choice_delta.tool_call_id,
                name=choice_delta.name,
                content_delta=choice_delta.content,
            ),
        ))
        
    # These are assistant messages
    elif choice_delta.content is not None:
        deltas.append(StreamTaskMessageDelta(
            parent_task_message=parent_task_message,
            delta=TextDelta(
                type=DeltaType.TEXT,
                text_delta=choice_delta.content,
            ),
        ))
        
    return deltas

def convert_choice_delta_to_message_content(choice_delta: ChoiceDelta) -> TaskMessageContent:
    """
    This function converts a ChoiceDelta to a TaskMessageContent object.
    Args:
        choice_delta: The ChoiceDelta to convert.
    Returns:
        A TaskMessageContent object.
    """
    # This converts a ChoiceDelta to a TaskMessage which will instantiate "the box" to send to client
    if choice_delta.tool_calls is not None:
        # since we are streaming we can assume we onl need to create a message for the first tool call
        return ToolRequestContent(
            author="agent",
            name=choice_delta.tool_calls[0].function.name,
            tool_call_id=choice_delta.tool_calls[0].id,
            arguments={}, # have to start this empty since we are streaming
        )
    elif choice_delta.role == "tool":
        return ToolResponseContent(
            author="agent",
            name=choice_delta.name,
            tool_call_id=choice_delta.tool_call_id,
            content='', # starting empty because we add to it
        )
    elif choice_delta.role == "assistant":
        return TextContent(
            author="agent",
            content='', # starting empty because we add to it
        )
    raise ValueError(f"Unknown role: {choice_delta.role}. Failed to convert to TaskMessage")

async def convert_oldowan_message_to_stream_task_message_full(
        id_to_streaming_context: Dict[str, StreamingTaskMessageContext],
        oldowan_message: Union[ChatCompletionMessage, ToolMessage],
    ) -> List[StreamTaskMessageFull]:
    """
    This function converts an Oldowan message to a list of StreamTaskMessageFull objects.
    Args:
        task_messages: A dictionary of task messages.
        task_id: The task id.
        oldowan_message: The Oldowan message to convert.
    Returns:
        A list of StreamTaskMessageFull objects.
    """

    if isinstance(oldowan_message, ChatCompletionMessage):
        # First create all tool calls
        if oldowan_message.tool_calls is not None:
            for tool_call in oldowan_message.tool_calls:
                task_message_full = StreamTaskMessageFull(
                    parent_task_message=id_to_streaming_context[tool_call.id].task_message,
                    content=ToolRequestContent(
                        author="agent",
                        name=tool_call.function.name,
                        tool_call_id=tool_call.id,
                        arguments=json.loads(tool_call.function.arguments),
                    ),
                )
                await id_to_streaming_context[tool_call.id].stream_update(
                    update=task_message_full,
                )
                

        # Create the assistant messages
        if oldowan_message.content is not None:
            task_message_full = StreamTaskMessageFull(
                parent_task_message=id_to_streaming_context[oldowan_message.id].task_message,
                content=TextContent(
                    author="agent",
                    content=oldowan_message.content,
                ),
            )
            await id_to_streaming_context[oldowan_message.id].stream_update(
                update=task_message_full,
            )

    # Finally create the tool responses
    elif isinstance(oldowan_message, ToolMessage):
        task_message_full = StreamTaskMessageFull(
            parent_task_message=id_to_streaming_context[oldowan_message.tool_call_id + TOOL_RESPONSE_ID_SUFFIX].task_message,
            content=ToolResponseContent(
                author="agent",
                name=oldowan_message.name,
                content=oldowan_message.content,
                tool_call_id=oldowan_message.tool_call_id,
            ),
        )
        await id_to_streaming_context[oldowan_message.tool_call_id + TOOL_RESPONSE_ID_SUFFIX].stream_update(
            update=task_message_full,
        )

def get_oldowan_message_ids(oldowan_message: Union[ChatCompletionMessage, ToolMessage]) -> List[str]:
    """
    This function gets the ids of the oldowan message.
    Args:
        oldowan_message: The Oldowan message to get the ids of.
    Returns:
        A list of ids.
    """
    message_ids = []
    if isinstance(oldowan_message, ChatCompletionMessage):
        # check that there is content
        if oldowan_message.content is not None:
            message_ids.append(oldowan_message.id)

        # check if there are tool calls
        if oldowan_message.tool_calls is not None:
            for tool_call in oldowan_message.tool_calls:
                message_ids.append(tool_call.id)

    elif isinstance(oldowan_message, ToolMessage):
        message_ids.append(oldowan_message.tool_call_id + TOOL_RESPONSE_ID_SUFFIX)
    
    return message_ids

# This will eventually become adk.providers.oldowan.stream_agent_async_auto_send
async def stream_oldowan_agent_async_auto_send(messages: List[Message], task_id: str, span: Span, simple_agent_acompletion_fn: Callable) -> List[Message]:
    """
    Stream an Oldowan agent response to the client.
    Args:
        messages: The messages to send to the agent.
        task_id: The task id.
        span: The span to use for tracing.
    Returns:
        AsyncGenerator[TaskMessageUpdate, None]: A generator of task message updates.
    """
    response_stream = await simple_agent_acompletion_fn(messages=messages)

    # This is used to create the current TaskMessage object
    cur_task_message_id = None

    # This maps id either from message object, tool_call, or tool_response to the TaskMessage object    
    id_to_streaming_context = {}

    # These are messages that have already been sent in "full"
    persisted_messages = []
    events = []

    # These are ChoiceDelta objects
    async for event in response_stream:
        print(event)
        if event.role is not None:
            # if there is a tool call made then check if its a new tool_call_id
            if event.tool_calls is not None and event.tool_calls[0].id is not None and event.tool_calls[0].id not in id_to_streaming_context:
                print(f"Role changed: {event.role}")
                print(f"Tool call id changed: {event.tool_calls[0].id}")
                cur_task_message_id = event.tool_calls[0].id
                streaming_context = adk.streaming.streaming_task_message_context(
                    task_id=task_id,
                    initial_content=convert_choice_delta_to_message_content(event),
                )
                id_to_streaming_context[event.tool_calls[0].id] = await streaming_context.open()
                print(f"Created streaming context for tool call: {id_to_streaming_context[event.tool_calls[0].id].task_message}")
                

            # If you are in a tool response, you should check that either the tool_call_id has changed or your last type was not tool
            elif event.role == "tool" and (event.tool_call_id + TOOL_RESPONSE_ID_SUFFIX not in id_to_streaming_context):
                print(f"Role changed: {event.role}")
                print(f"Tool Response id: {event.tool_call_id + TOOL_RESPONSE_ID_SUFFIX}")
                cur_task_message_id = event.tool_call_id + TOOL_RESPONSE_ID_SUFFIX
                streaming_context = adk.streaming.streaming_task_message_context(
                    task_id=task_id,
                    initial_content=convert_choice_delta_to_message_content(event),
                )
                id_to_streaming_context[event.tool_call_id + TOOL_RESPONSE_ID_SUFFIX] = await streaming_context.open()
                print(f"Created streaming context for tool response: {id_to_streaming_context[event.tool_call_id + TOOL_RESPONSE_ID_SUFFIX].task_message}")


            elif event.role == "assistant" and event.content is not None and event.id not in id_to_streaming_context: # this is an assistant message
                print(f"Role is: {event.role}")
                assert hasattr(event, "id"), "Event does not have an id, please upgrade to latest oldowan"
                print(f"Event id: {event.id}")
                cur_task_message_id = event.id
                streaming_context = adk.streaming.streaming_task_message_context(
                    task_id=task_id,
                    initial_content=convert_choice_delta_to_message_content(event),
                )
                id_to_streaming_context[event.id] = await streaming_context.open()
                print(f"Created streaming context for assistant message: {id_to_streaming_context[event.id].task_message}")

            

        # Now we can create the items to stream
        # NOTE: key assumption is that ChoiceDeltaToolCall can only apply to one tool call at a time.
        for task_message_delta in convert_choice_delta_to_stream_task_message_deltas(event, parent_task_message=id_to_streaming_context[cur_task_message_id].task_message):
            streaming_context = id_to_streaming_context[cur_task_message_id]
            await streaming_context.stream_update(
                update=task_message_delta,
            )

        events.append(event)

        # Issue is that we can either have an oldowan message before a task message has been created OR task message before the oldowan message
        # this is because tool response messages are added to messages immediately, but streamed one after the other.
        # For each oldowan message, if we haven't persisted it yet, then do so
        for idx, oldowan_message in enumerate(response_stream.messages):
            if oldowan_message not in persisted_messages and all([id in id_to_streaming_context for id in get_oldowan_message_ids(oldowan_message)]):
                async with adk.tracing.span(
                    trace_id=task_id,
                    parent_id=span.id,
                    name=f"Message {idx}",
                    input=messages + response_stream.messages[:idx], # input messages to this message
                ) as message_span:
                    message_span.output = oldowan_message

                # Send the full messages now that they are done
                await convert_oldowan_message_to_stream_task_message_full(
                    id_to_streaming_context=id_to_streaming_context,
                    oldowan_message=oldowan_message
                )
                
                print(f"Persisted message: {oldowan_message}")
                persisted_messages.append(oldowan_message)

    # Stream the last object
    async with adk.tracing.span(
        trace_id=task_id,
        parent_id=span.id,
        name=f"Message {len(response_stream.messages)}",
        input=messages + response_stream.messages[:-1],
    ) as message_span:
        message_span.output = response_stream.messages[-1]

    # Persist the last message to the DB
    await convert_oldowan_message_to_stream_task_message_full(
        id_to_streaming_context=id_to_streaming_context, 
        oldowan_message=response_stream.messages[-1]
    )
    print(f"Persisted message: {response_stream.messages[-1]}")
    persisted_messages.append(response_stream.messages[-1])

    # Close all the streaming contexts
    for streaming_context in id_to_streaming_context.values():
        if not streaming_context._is_closed:
            print(f"Closing streaming context for message ID: {streaming_context.task_message.id}. Is closed: {streaming_context._is_closed}")
            await streaming_context.close()

    # Aggregate the messages and store the output
    return response_stream.messages
    

@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    # Upon task creation, we initialize the task state with a system message.
    # This will be fetched by the `on_task_event_send` handler when each event is sent.
    state = StateModel(
        simple_agent_completion_config=SimpleAgentCompletionConfig(
            model="openai/gpt-4o",
            tools=["google_search", "think"],
            max_tokens=8192,
            stream=True,
        ),
        messages=[],
        turn_number=0,
    )
    assert all([tool in TOOL_DICT for tool in state.simple_agent_completion_config.tools]), f"Invalid tool: {state.simple_agent_completion_config.tools}"
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

    print(f"Received event: {params.event.content}")
    await adk.messages.create(
        task_id=params.task.id,
        trace_id=params.task.id,
        content=params.event.content,
    )

    # Try to retrieve the state. If it doesn't exist, create it.
    task_state = await adk.state.get_by_task_and_agent(task_id=params.task.id, agent_id=params.agent.id)
    state = StateModel.model_validate(task_state.state)

    messages = state.messages
    
    #########################################################
    # 4. Call an LLM to respond to the user's message and stream the response to the client.
    #########################################################
    print(f"Calling LLM with model {state.simple_agent_completion_config.model_dump_json()} and messages {messages}")

    # Add the user's message to the conversation history
    state.messages.append(UserMessage(content=params.event.content.content))

    # The Agentex server automatically commits input and output messages to the database so you don't need to do this yourself, simply process the input content and return the output content.
    async with adk.tracing.span(
        trace_id=params.task.id,
        name=f"Turn {state.turn_number}",
        input=state,
    ) as span:
        simple_agent_completion_fn = partial(
            simple_agent_acompletion,
            model=state.simple_agent_completion_config.model,
            tools=[TOOL_DICT[tool] for tool in state.simple_agent_completion_config.tools],
            max_tokens=state.simple_agent_completion_config.max_tokens,
            stream=state.simple_agent_completion_config.stream,
        )

        # Stream the response and collect the generated messages
        messages = await stream_oldowan_agent_async_auto_send(messages=messages, task_id=params.task.id, span=span, simple_agent_acompletion_fn=simple_agent_completion_fn)
            
        # The generated messages are accessible from the span output
        state.messages.extend(messages)

    state.turn_number += 1
    
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