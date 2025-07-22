import os
from typing import Dict, List, Optional
from contextlib import AsyncExitStack, asynccontextmanager
import json 

from agentex.lib import adk
from agentex.lib.core.services.adk.streaming import StreamingTaskMessageContext
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.acp import CancelTaskParams, CreateTaskParams, SendEventParams
from agentex.lib.types.fastacp import AgenticACPConfig
from agentex.lib.types.task_message_updates import (
    StreamTaskMessageDelta, 
    StreamTaskMessageFull,
    TextDelta,
)
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel
from agentex.types.text_content import TextContent
from agentex.types.task_message_content import ToolRequestContent, ToolResponseContent

from agents import Agent, Runner
from agents.mcp import MCPServerStdio
from mcp import StdioServerParameters
from openai.types.responses import (
    ResponseCompletedEvent,
    ResponseFunctionToolCall,
    ResponseOutputItemDoneEvent,
    ResponseTextDeltaEvent,
)
from pydantic import BaseModel

logger = make_logger(__name__)


# Create an ACP server

# !!! Warning: Because "Agentic" ACPs are designed to be fully asynchronous, race conditions can occur if parallel events are sent. It is highly recommended to use the "temporal" type in the AgenticACPConfig instead to handle complex use cases. The "base" ACP is only designed to be used for simple use cases and for learning purposes.
acp = FastACP.create(
    acp_type="agentic",
    config=AgenticACPConfig(type="base"),
)

class StateModel(BaseModel):
    input_list: List[dict]
    turn_number: int


MCP_SERVERS = [
    StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-sequential-thinking"],
    ),
    StdioServerParameters(
        command="uvx",
        args=["openai-websearch-mcp"],
        env={
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "")
        }
    ),
]


@acp.on_task_create
async def handle_task_create(params: CreateTaskParams):
    # Upon task creation, we initialize the task state with a system message.
    # This will be fetched by the `on_task_event_send` handler when each event is sent.
    state = StateModel(
        input_list=[],
        turn_number=0,
    )
    await adk.state.create(task_id=params.task.id, agent_id=params.agent.id, state=state)

@acp.on_task_event_send
async def handle_event_send(params: SendEventParams):
    # !!! Warning: Because "Agentic" ACPs are designed to be fully asynchronous, race conditions can occur if parallel events are sent. It is highly recommended to use the "temporal" type in the AgenticACPConfig instead to handle complex use cases. The "base" ACP is only designed to be used for simple use cases and for learning purposes.

    if not params.event.content:
        return

    if params.event.content.type != "text":
        raise ValueError(f"Expected text message, got {params.event.content.type}")

    if params.event.content.author != "user":
        raise ValueError(f"Expected user message, got {params.event.content.author}")


    # Retrieve the task state. Each event is handled as a new turn, so we need to get the state for the current turn.
    task_state = await adk.state.get_by_task_and_agent(task_id=params.task.id, agent_id=params.agent.id)
    state = StateModel.model_validate(task_state.state)
    state.turn_number += 1

    # Add the new user message to the message history
    state.input_list.append({"role": "user", "content": params.event.content.content})
    
    async with adk.tracing.span(
        trace_id=params.task.id,
        name=f"Turn {state.turn_number}",
        input=state
    ) as span:
        # Echo back the user's message so it shows up in the UI. This is not done by default so the agent developer has full control over what is shown to the user.
        await adk.messages.create(
            task_id=params.task.id,
            trace_id=params.task.id,
            content=params.event.content,
            parent_span_id=span.id if span else None,
        )

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
        # (👋) Call an LLM to respond to the user's message using custom streaming
        #########################################################

        # This demonstrates advanced streaming patterns using adk.streaming.
        # We'll show two different streaming approaches:
        # 1. Simple streaming with context managers for complete messages (tool calls)
        # 2. Delta-based streaming for incremental text responses
        run_result = await run_openai_agent_with_custom_streaming(
            task_id=params.task.id,
            trace_id=params.task.id,
            input_list=state.input_list,
            mcp_server_params=MCP_SERVERS,
            agent_name="Tool-Enabled Assistant",
            agent_instructions="""You are a helpful assistant that can answer questions using various tools.
            You have access to sequential thinking and web search capabilities through MCP servers.
            Use these tools when appropriate to provide accurate and well-reasoned responses.""",
            parent_span_id=span.id if span else None,
        )

        state.input_list = run_result.to_input_list()

        # Store the messages in the task state for the next turn
        await adk.state.update(
            state_id=task_state.id,
            task_id=params.task.id,
            agent_id=params.agent.id,
            state=state,
            trace_id=params.task.id,
            parent_span_id=span.id if span else None,
        )

        # Set the span output to the state for the next turn
        span.output = state

@acp.on_task_cancel
async def handle_task_cancel(params: CancelTaskParams):
    """Default task cancel handler"""
    logger.info(f"Task canceled: {params.task}")


########################################################
# Helper functions that integrate Agentex primitives with other SDKs like OpenAI Agents
########################################################


@asynccontextmanager
async def mcp_server_context(mcp_server_params: list[StdioServerParameters]):
    """Context manager for MCP servers."""
    servers = []
    for params in mcp_server_params:
        server = MCPServerStdio(
            name=f"Server: {params.command}", 
            params=params.model_dump(), 
            cache_tools_list=True,
            client_session_timeout_seconds=60,
        )
        servers.append(server)

    async with AsyncExitStack() as stack:
        for server in servers:
            await stack.enter_async_context(server)
        yield servers


def redact_mcp_server_params(
    mcp_server_params: list[StdioServerParameters],
) -> list[StdioServerParameters]:
    """Redact MCP server params."""
    return [
        StdioServerParameters(
            **{k: v for k, v in server_param.model_dump().items() if k != "env"},
            env={k: "********" for k in server_param.env} if server_param.env else None,
        )
        for server_param in mcp_server_params
    ]


async def run_openai_agent_with_custom_streaming(
    task_id: str,
    trace_id: str,
    input_list: list[Dict],
    mcp_server_params: list[StdioServerParameters],
    agent_name: str,
    agent_instructions: str,
    parent_span_id: Optional[str] = None,
):
    """
    Run an OpenAI agent with custom streaming using adk.streaming.

    This demonstrates advanced streaming patterns using adk.streaming.
    We'll show two different streaming approaches:
    1. Simple streaming with context managers for complete messages (tool calls)
    2. Delta-based streaming for incremental text responses
    """

    tool_call_map: Dict[str, ResponseFunctionToolCall] = {}

    redacted_mcp_server_params = redact_mcp_server_params(mcp_server_params)

    result = None
    async with adk.tracing.span(
        trace_id=trace_id,
        name="run_agent_with_custom_streaming",
        input={
            "input_list": input_list,
            "mcp_server_params": redacted_mcp_server_params,
            "agent_name": agent_name,
            "agent_instructions": agent_instructions,
        },
        parent_id=parent_span_id,
    ) as span:
        async with mcp_server_context(mcp_server_params) as servers:
            agent = Agent(
                name=agent_name,
                instructions=agent_instructions,
                mcp_servers=servers,
            )

            # Run with streaming enabled
            result = Runner.run_streamed(starting_agent=agent, input=input_list)

            #########################################################
            # (👋) For complete messages like tool calls we will use a with block to create a streaming context, but for text deltas we will use a streaming context that is created and closed manually. To make sure we close all streaming contexts we will track the item_id and close them all at the end.
            #########################################################

            item_id_to_streaming_context: Dict[str, StreamingTaskMessageContext] = {}
            unclosed_item_ids: set[str] = set()

            try:
                # Process streaming events with TaskMessage creation
                async for event in result.stream_events():

                    if event.type == "run_item_stream_event":
                        if event.item.type == "tool_call_item":
                            tool_call_item = event.item.raw_item
                            tool_call_map[tool_call_item.call_id] = tool_call_item

                            logger.info(f"Tool call item: {tool_call_item}")

                            tool_request_content = ToolRequestContent(
                                author="agent",
                                tool_call_id=tool_call_item.call_id,
                                name=tool_call_item.name,
                                arguments=json.loads(tool_call_item.arguments),
                            )

                            # (👋) Create a streaming context for the tool call
                            # Since a tool call is a complete message, we can use a with block to create a streaming context. This will take care of creating a TaskMessage, sending a START event, and sending a DONE event when the context is closed. Of course you will also want to stream the content of the tool call so clients that are subscribed to streaming updates to the task will see the tool call.
                            async with adk.streaming.streaming_task_message_context(
                                task_id=task_id,
                                initial_content=tool_request_content,
                            ) as streaming_context:
                                # The message has already been persisted, but we still need to send an upda
                                await streaming_context.stream_update(
                                    update=StreamTaskMessageFull(
                                        parent_task_message=streaming_context.task_message,
                                        content=tool_request_content,
                                        content_type=tool_request_content.type,
                                    ),
                                )

                        elif event.item.type == "tool_call_output_item":
                            tool_output_item = event.item.raw_item

                            tool_response_content = ToolResponseContent(
                                author="agent",
                                tool_call_id=tool_output_item["call_id"],
                                name=tool_call_map[tool_output_item["call_id"]].name,
                                content=tool_output_item["output"],
                            )

                            # (👋) Create a streaming context for the tool call output
                            # Since a tool call output is a complete message, we can use a with block to create a streaming context. This will take care of creating a TaskMessage, sending a START event, and sending a DONE event when the context is closed. Of course you will also want to stream the content of the tool call output so clients that are subscribed to streaming updates to the task will see the tool call output.
                            async with adk.streaming.streaming_task_message_context(
                                task_id=task_id,
                                initial_content=tool_response_content,
                            ) as streaming_context:
                                # The message has already been persisted, but we still need to send an update
                                await streaming_context.stream_update(
                                    update=StreamTaskMessageFull(
                                        parent_task_message=streaming_context.task_message,
                                        content=tool_response_content,
                                        content_type=tool_response_content.type,
                                    ),
                                )

                    elif event.type == "raw_response_event":
                        if isinstance(event.data, ResponseTextDeltaEvent):
                            # Handle text delta
                            item_id = event.data.item_id

                            # (👋) Create a streaming context for the text delta
                            # Since a text delta is a partial message, we will create a streaming context manually without a with block because we need to persist the context across the for loop.
                            if item_id not in item_id_to_streaming_context:
                                streaming_context = adk.streaming.streaming_task_message_context(
                                    task_id=task_id,
                                    initial_content=TextContent(
                                        author="agent",
                                        content="",
                                    ),
                                )
                                # (👋) Open the streaming context manually
                                # This will create a TaskMessage and send a START event for you.
                                item_id_to_streaming_context[item_id] = await streaming_context.open()

                                # (👋) Add the item_id to the set of unclosed item_ids
                                # This will allow us to close any lingering streaming context when the agent is done.
                                unclosed_item_ids.add(item_id)
                            else:
                                streaming_context = item_id_to_streaming_context[item_id]

                            # (👋) Stream the delta through the streaming service
                            # This will send a DELTA event. The context manager will accumulate the content for you into a final message when you close the context.
                            await streaming_context.stream_update(
                                update=StreamTaskMessageDelta(
                                    parent_task_message=streaming_context.task_message,
                                    delta=TextDelta(text_delta=event.data.delta),
                                ),
                            )

                        elif isinstance(event.data, ResponseOutputItemDoneEvent):
                            # Handle item completion
                            item_id = event.data.item.id

                            # (👋) Close the streaming context
                            # This will send a DONE event and update the persisted message.
                            if item_id in item_id_to_streaming_context:
                                streaming_context = item_id_to_streaming_context[item_id]
                                await streaming_context.close()
                                unclosed_item_ids.remove(item_id)

                        elif isinstance(event.data, ResponseCompletedEvent):
                            # (👋) Close all remaining streaming contexts
                            # This will send a DONE event and update the persisted messages for all remaining streaming contents. Normally this won't be needed if all messages are closed by the time the agent is done.
                            for item_id in unclosed_item_ids:
                                streaming_context = item_id_to_streaming_context[item_id]
                                await streaming_context.close()
                                unclosed_item_ids.remove(item_id)

            finally:
                # (👋) Close all remaining streaming contexts
                # This will send a DONE event and update the persisted messages for all remaining streaming contents. Normally this won't be needed, but we do it in case any errors occur.
                for item_id in unclosed_item_ids:
                    streaming_context = item_id_to_streaming_context[item_id]
                    await streaming_context.close()
                    unclosed_item_ids.remove(item_id)
        if span:
            span.output = {
                "new_items": [
                    item.raw_item.model_dump()
                    if isinstance(item.raw_item, BaseModel)
                    else item.raw_item
                    for item in result.new_items
                ],
                "final_output": result.final_output,
            }
    return result
