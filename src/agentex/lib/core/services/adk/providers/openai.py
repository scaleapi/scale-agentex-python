# Standard library imports
import json
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, Literal

from agents import Agent, Runner, RunResult, RunResultStreaming
from agents.agent import StopAtTools, ToolsToFinalOutputFunction
from agents.mcp import MCPServerStdio
from mcp import StdioServerParameters
from openai.types.responses import (
    ResponseCompletedEvent,
    ResponseFunctionToolCall,
    ResponseOutputItemDoneEvent,
    ResponseTextDeltaEvent,
)
from pydantic import BaseModel

# Local imports
from agentex import AsyncAgentex
from agentex.lib.core.services.adk.streaming import (
    StreamingService,
    StreamingTaskMessageContext,
)
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.lib.types.task_message_updates import (
    StreamTaskMessageDelta,
    StreamTaskMessageFull,
    TextDelta,
)
from agentex.types.task_message_content import (
    TextContent,
    ToolRequestContent,
    ToolResponseContent,
)
from agentex.lib.utils import logging
from agentex.lib.utils.mcp import redact_mcp_server_params
from agentex.lib.utils.temporal import heartbeat_if_in_workflow

logger = logging.make_logger(__name__)


@asynccontextmanager
async def mcp_server_context(
    mcp_server_params: list[StdioServerParameters],
    mcp_timeout_seconds: int | None = None,
):
    """Context manager for MCP servers."""
    servers = []
    for params in mcp_server_params:
        server = MCPServerStdio(
            name=f"Server: {params.command}",
            params=params.model_dump(),
            cache_tools_list=True,
            client_session_timeout_seconds=mcp_timeout_seconds,
        )
        servers.append(server)

    async with AsyncExitStack() as stack:
        for server in servers:
            await stack.enter_async_context(server)
        yield servers


class OpenAIService:
    """Service for OpenAI agent operations using the agents library."""

    def __init__(
        self,
        agentex_client: AsyncAgentex | None = None,
        streaming_service: StreamingService | None = None,
        tracer: AsyncTracer | None = None,
    ):
        self.agentex_client = agentex_client
        self.streaming_service = streaming_service
        self.tracer = tracer

    async def run_agent(
        self,
        input_list: list[dict[str, Any]],
        mcp_server_params: list[StdioServerParameters],
        agent_name: str,
        agent_instructions: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        handoff_description: str | None = None,
        handoffs: list[BaseModel] | None = None,
        model: str | None = None,
        model_settings: BaseModel | None = None,
        tools: list[BaseModel] | None = None,
        output_type: type[Any] | None = None,
        tool_use_behavior: (
            Literal["run_llm_again", "stop_on_first_tool"]
            | StopAtTools
            | ToolsToFinalOutputFunction
        ) = "run_llm_again",
        mcp_timeout_seconds: int | None = None,
    ) -> RunResult:
        """
        Run an agent without streaming or TaskMessage creation.

        Args:
            input_list: List of input data for the agent.
            mcp_server_params: MCP server parameters for the agent.
            agent_name: The name of the agent to run.
            agent_instructions: Instructions for the agent.
            trace_id: Optional trace ID for tracing.
            parent_span_id: Optional parent span ID for tracing.
            handoff_description: Optional description of the handoff.
            handoffs: Optional list of handoffs.
            model: Optional model to use.
            model_settings: Optional model settings.
            tools: Optional list of tools.
            output_type: Optional output type.
            tool_use_behavior: Optional tool use behavior.
            mcp_timeout_seconds: Optional param to set the timeout threshold for the MCP servers. Defaults to 5 seconds.

        Returns:
            SerializableRunResult: The result of the agent run.
        """
        redacted_params = redact_mcp_server_params(mcp_server_params)

        trace = self.tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="run_agent",
            input={
                "input_list": input_list,
                "mcp_server_params": redacted_params,
                "agent_name": agent_name,
                "agent_instructions": agent_instructions,
                "handoff_description": handoff_description,
                "handoffs": handoffs,
                "model": model,
                "model_settings": model_settings,
                "tools": tools,
                "output_type": output_type,
                "tool_use_behavior": tool_use_behavior,
            },
        ) as span:
            heartbeat_if_in_workflow("run agent")

            async with mcp_server_context(
                mcp_server_params, mcp_timeout_seconds
            ) as servers:
                tools = [tool.to_oai_function_tool() for tool in tools] if tools else []
                handoffs = (
                    [Agent(**handoff.model_dump()) for handoff in handoffs]
                    if handoffs
                    else []
                )

                agent_kwargs = {
                    "name": agent_name,
                    "instructions": agent_instructions,
                    "mcp_servers": servers,
                    "handoff_description": handoff_description,
                    "handoffs": handoffs,
                    "model": model,
                    "tools": tools,
                    "output_type": output_type,
                    "tool_use_behavior": tool_use_behavior,
                }
                if model_settings is not None:
                    agent_kwargs["model_settings"] = (
                        model_settings.to_oai_model_settings()
                    )

                agent = Agent(**agent_kwargs)

                # Run without streaming
                result = await Runner.run(starting_agent=agent, input=input_list)

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

    async def run_agent_auto_send(
        self,
        task_id: str,
        input_list: list[dict[str, Any]],
        mcp_server_params: list[StdioServerParameters],
        agent_name: str,
        agent_instructions: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        handoff_description: str | None = None,
        handoffs: list[BaseModel] | None = None,
        model: str | None = None,
        model_settings: BaseModel | None = None,
        tools: list[BaseModel] | None = None,
        output_type: type[Any] | None = None,
        tool_use_behavior: (
            Literal["run_llm_again", "stop_on_first_tool"]
            | StopAtTools
            | ToolsToFinalOutputFunction
        ) = "run_llm_again",
        mcp_timeout_seconds: int | None = None,
    ) -> RunResult:
        """
        Run an agent with automatic TaskMessage creation.

        Args:
            task_id: The ID of the task to run the agent for.
            input_list: List of input data for the agent.
            mcp_server_params: MCP server parameters for the agent.
            agent_name: The name of the agent to run.
            agent_instructions: Instructions for the agent.
            trace_id: Optional trace ID for tracing.
            parent_span_id: Optional parent span ID for tracing.
            handoff_description: Optional description of the handoff.
            handoffs: Optional list of handoffs.
            model: Optional model to use.
            model_settings: Optional model settings.
            tools: Optional list of tools.
            output_type: Optional output type.
            tool_use_behavior: Optional tool use behavior.
            mcp_timeout_seconds: Optional param to set the timeout threshold for the MCP servers. Defaults to 5 seconds.

        Returns:
            SerializableRunResult: The result of the agent run.
        """
        if self.streaming_service is None:
            raise ValueError("StreamingService must be available for auto_send methods")
        if self.agentex_client is None:
            raise ValueError("Agentex client must be provided for auto_send methods")

        redacted_params = redact_mcp_server_params(mcp_server_params)

        trace = self.tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="run_agent_auto_send",
            input={
                "task_id": task_id,
                "input_list": input_list,
                "mcp_server_params": redacted_params,
                "agent_name": agent_name,
                "agent_instructions": agent_instructions,
                "handoff_description": handoff_description,
                "handoffs": handoffs,
                "model": model,
                "model_settings": model_settings,
                "tools": tools,
                "output_type": output_type,
                "tool_use_behavior": tool_use_behavior,
            },
        ) as span:
            heartbeat_if_in_workflow("run agent auto send")

            async with mcp_server_context(
                mcp_server_params, mcp_timeout_seconds
            ) as servers:
                tools = [tool.to_oai_function_tool() for tool in tools] if tools else []
                handoffs = (
                    [Agent(**handoff.model_dump()) for handoff in handoffs]
                    if handoffs
                    else []
                )
                agent_kwargs = {
                    "name": agent_name,
                    "instructions": agent_instructions,
                    "mcp_servers": servers,
                    "handoff_description": handoff_description,
                    "handoffs": handoffs,
                    "model": model,
                    "tools": tools,
                    "output_type": output_type,
                    "tool_use_behavior": tool_use_behavior,
                }
                if model_settings is not None:
                    agent_kwargs["model_settings"] = (
                        model_settings.to_oai_model_settings()
                    )

                agent = Agent(**agent_kwargs)

                # Run without streaming
                result = await Runner.run(starting_agent=agent, input=input_list)

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

                tool_call_map: dict[str, ResponseFunctionToolCall] = {}

                for item in result.new_items:
                    if item.type == "message_output_item":
                        text_content = TextContent(
                            author="agent",
                            content=item.raw_item.content[0].text,
                        )
                        # Create message for the final result using streaming context
                        async with (
                            self.streaming_service.streaming_task_message_context(
                                task_id=task_id,
                                initial_content=text_content,
                            ) as streaming_context
                        ):
                            await streaming_context.stream_update(
                                update=StreamTaskMessageFull(
                                    parent_task_message=streaming_context.task_message,
                                    content=text_content,
                                ),
                            )

                    elif item.type == "tool_call_item":
                        tool_call_map[item.raw_item.call_id] = item.raw_item

                        tool_request_content = ToolRequestContent(
                            author="agent",
                            tool_call_id=item.raw_item.call_id,
                            name=item.raw_item.name,
                            arguments=json.loads(item.raw_item.arguments),
                        )

                        # Create tool request using streaming context
                        async with (
                            self.streaming_service.streaming_task_message_context(
                                task_id=task_id,
                                initial_content=tool_request_content,
                            ) as streaming_context
                        ):
                            await streaming_context.stream_update(
                                update=StreamTaskMessageFull(
                                    parent_task_message=streaming_context.task_message,
                                    content=tool_request_content,
                                ),
                            )

                    elif item.type == "tool_call_output_item":
                        tool_output_item = item.raw_item

                        tool_response_content = ToolResponseContent(
                            author="agent",
                            tool_call_id=tool_output_item["call_id"],
                            name=tool_call_map[tool_output_item["call_id"]].name,
                            content=tool_output_item["output"],
                        )
                        # Create tool response using streaming context
                        async with (
                            self.streaming_service.streaming_task_message_context(
                                task_id=task_id,
                                initial_content=tool_response_content,
                            ) as streaming_context
                        ):
                            await streaming_context.stream_update(
                                update=StreamTaskMessageFull(
                                    parent_task_message=streaming_context.task_message,
                                    content=tool_response_content,
                                ),
                            )

                # Convert to serializable result
        return result

    async def run_agent_streamed(
        self,
        input_list: list[dict[str, Any]],
        mcp_server_params: list[StdioServerParameters],
        agent_name: str,
        agent_instructions: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        handoff_description: str | None = None,
        handoffs: list[BaseModel] | None = None,
        model: str | None = None,
        model_settings: BaseModel | None = None,
        tools: list[BaseModel] | None = None,
        output_type: type[Any] | None = None,
        tool_use_behavior: (
            Literal["run_llm_again", "stop_on_first_tool"]
            | StopAtTools
            | ToolsToFinalOutputFunction
        ) = "run_llm_again",
        mcp_timeout_seconds: int | None = None,
    ) -> RunResultStreaming:
        """
        Run an agent with streaming enabled but no TaskMessage creation.

        Args:
            input_list: List of input data for the agent.
            mcp_server_params: MCP server parameters for the agent.
            agent_name: The name of the agent to run.
            agent_instructions: Instructions for the agent.
            trace_id: Optional trace ID for tracing.
            parent_span_id: Optional parent span ID for tracing.
            handoff_description: Optional description of the handoff.
            handoffs: Optional list of handoffs.
            model: Optional model to use.
            model_settings: Optional model settings.
            tools: Optional list of tools.
            output_type: Optional output type.
            tool_use_behavior: Optional tool use behavior.
            mcp_timeout_seconds: Optional param to set the timeout threshold for the MCP servers. Defaults to 5 seconds.

        Returns:
            RunResultStreaming: The result of the agent run with streaming.
        """
        trace = self.tracer.trace(trace_id)
        redacted_params = redact_mcp_server_params(mcp_server_params)

        async with trace.span(
            parent_id=parent_span_id,
            name="run_agent_streamed",
            input={
                "input_list": input_list,
                "mcp_server_params": redacted_params,
                "agent_name": agent_name,
                "agent_instructions": agent_instructions,
                "handoff_description": handoff_description,
                "handoffs": handoffs,
                "model": model,
                "model_settings": model_settings,
                "tools": tools,
                "output_type": output_type,
                "tool_use_behavior": tool_use_behavior,
            },
        ) as span:
            heartbeat_if_in_workflow("run agent streamed")

            async with mcp_server_context(
                mcp_server_params, mcp_timeout_seconds
            ) as servers:
                tools = [tool.to_oai_function_tool() for tool in tools] if tools else []
                handoffs = (
                    [Agent(**handoff.model_dump()) for handoff in handoffs]
                    if handoffs
                    else []
                )
                agent_kwargs = {
                    "name": agent_name,
                    "instructions": agent_instructions,
                    "mcp_servers": servers,
                    "handoff_description": handoff_description,
                    "handoffs": handoffs,
                    "model": model,
                    "tools": tools,
                    "output_type": output_type,
                    "tool_use_behavior": tool_use_behavior,
                }
                if model_settings is not None:
                    agent_kwargs["model_settings"] = (
                        model_settings.to_oai_model_settings()
                    )

                agent = Agent(**agent_kwargs)

                # Run with streaming (but no TaskMessage creation)
                result = Runner.run_streamed(starting_agent=agent, input=input_list)

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

    async def run_agent_streamed_auto_send(
        self,
        task_id: str,
        input_list: list[dict[str, Any]],
        mcp_server_params: list[StdioServerParameters],
        agent_name: str,
        agent_instructions: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        handoff_description: str | None = None,
        handoffs: list[BaseModel] | None = None,
        model: str | None = None,
        model_settings: BaseModel | None = None,
        tools: list[BaseModel] | None = None,
        output_type: type[Any] | None = None,
        tool_use_behavior: (
            Literal["run_llm_again", "stop_on_first_tool"]
            | StopAtTools
            | ToolsToFinalOutputFunction
        ) = "run_llm_again",
        mcp_timeout_seconds: int | None = None,
    ) -> RunResultStreaming:
        """
        Run an agent with streaming enabled and automatic TaskMessage creation.

        Args:
            task_id: The ID of the task to run the agent for.
            input_list: List of input data for the agent.
            mcp_server_params: MCP server parameters for the agent.
            agent_name: The name of the agent to run.
            agent_instructions: Instructions for the agent.
            trace_id: Optional trace ID for tracing.
            parent_span_id: Optional parent span ID for tracing.
            handoff_description: Optional description of the handoff.
            handoffs: Optional list of handoffs.
            model: Optional model to use.
            model_settings: Optional model settings.
            tools: Optional list of tools.
            output_type: Optional output type.
            tool_use_behavior: Optional tool use behavior.
            mcp_timeout_seconds: Optional param to set the timeout threshold for the MCP servers. Defaults to 5 seconds.

        Returns:
            RunResultStreaming: The result of the agent run with streaming.
        """
        if self.streaming_service is None:
            raise ValueError("StreamingService must be available for auto_send methods")
        if self.agentex_client is None:
            raise ValueError("Agentex client must be provided for auto_send methods")

        tool_call_map: dict[str, ResponseFunctionToolCall] = {}

        trace = self.tracer.trace(trace_id)
        redacted_params = redact_mcp_server_params(mcp_server_params)

        async with trace.span(
            parent_id=parent_span_id,
            name="run_agent_streamed_auto_send",
            input={
                "task_id": task_id,
                "input_list": input_list,
                "mcp_server_params": redacted_params,
                "agent_name": agent_name,
                "agent_instructions": agent_instructions,
                "handoff_description": handoff_description,
                "handoffs": handoffs,
                "model": model,
                "model_settings": model_settings,
                "tools": tools,
                "output_type": output_type,
                "tool_use_behavior": tool_use_behavior,
            },
        ) as span:
            heartbeat_if_in_workflow("run agent streamed auto send")

            async with mcp_server_context(
                mcp_server_params, mcp_timeout_seconds
            ) as servers:
                tools = [tool.to_oai_function_tool() for tool in tools] if tools else []
                handoffs = (
                    [Agent(**handoff.model_dump()) for handoff in handoffs]
                    if handoffs
                    else []
                )
                agent_kwargs = {
                    "name": agent_name,
                    "instructions": agent_instructions,
                    "mcp_servers": servers,
                    "handoff_description": handoff_description,
                    "handoffs": handoffs,
                    "model": model,
                    "tools": tools,
                    "output_type": output_type,
                    "tool_use_behavior": tool_use_behavior,
                }
                if model_settings is not None:
                    agent_kwargs["model_settings"] = (
                        model_settings.to_oai_model_settings()
                    )

                agent = Agent(**agent_kwargs)

                # Run with streaming
                result = Runner.run_streamed(starting_agent=agent, input=input_list)

                item_id_to_streaming_context: dict[
                    str, StreamingTaskMessageContext
                ] = {}
                unclosed_item_ids: set[str] = set()

                try:
                    # Process streaming events with TaskMessage creation
                    async for event in result.stream_events():
                        heartbeat_if_in_workflow(
                            "processing stream event with auto send"
                        )

                        if event.type == "run_item_stream_event":
                            if event.item.type == "tool_call_item":
                                tool_call_item = event.item.raw_item
                                tool_call_map[tool_call_item.call_id] = tool_call_item

                                tool_request_content = ToolRequestContent(
                                    author="agent",
                                    tool_call_id=tool_call_item.call_id,
                                    name=tool_call_item.name,
                                    arguments=json.loads(tool_call_item.arguments),
                                )

                                # Create tool request using streaming context (immediate completion)
                                async with (
                                    self.streaming_service.streaming_task_message_context(
                                        task_id=task_id,
                                        initial_content=tool_request_content,
                                    ) as streaming_context
                                ):
                                    # The message has already been persisted, but we still need to send an upda
                                    await streaming_context.stream_update(
                                        update=StreamTaskMessageFull(
                                            parent_task_message=streaming_context.task_message,
                                            content=tool_request_content,
                                        ),
                                    )

                            elif event.item.type == "tool_call_output_item":
                                tool_output_item = event.item.raw_item

                                tool_response_content = ToolResponseContent(
                                    author="agent",
                                    tool_call_id=tool_output_item["call_id"],
                                    name=tool_call_map[
                                        tool_output_item["call_id"]
                                    ].name,
                                    content=tool_output_item["output"],
                                )

                                # Create tool response using streaming context (immediate completion)
                                async with (
                                    self.streaming_service.streaming_task_message_context(
                                        task_id=task_id,
                                        initial_content=tool_response_content,
                                    ) as streaming_context
                                ):
                                    # The message has already been persisted, but we still need to send an update
                                    await streaming_context.stream_update(
                                        update=StreamTaskMessageFull(
                                            parent_task_message=streaming_context.task_message,
                                            content=tool_response_content,
                                        ),
                                    )

                        elif event.type == "raw_response_event":
                            if isinstance(event.data, ResponseTextDeltaEvent):
                                # Handle text delta
                                item_id = event.data.item_id

                                # Check if we already have a streaming context for this item
                                if item_id not in item_id_to_streaming_context:
                                    # Create a new streaming context for this item
                                    streaming_context = self.streaming_service.streaming_task_message_context(
                                        task_id=task_id,
                                        initial_content=TextContent(
                                            author="agent",
                                            content="",
                                        ),
                                    )
                                    # Open the streaming context
                                    item_id_to_streaming_context[
                                        item_id
                                    ] = await streaming_context.open()
                                    unclosed_item_ids.add(item_id)
                                else:
                                    streaming_context = item_id_to_streaming_context[
                                        item_id
                                    ]

                                # Stream the delta through the streaming service
                                await streaming_context.stream_update(
                                    update=StreamTaskMessageDelta(
                                        parent_task_message=streaming_context.task_message,
                                        delta=TextDelta(text_delta=event.data.delta),
                                    ),
                                )

                            elif isinstance(event.data, ResponseOutputItemDoneEvent):
                                # Handle item completion
                                item_id = event.data.item.id

                                # Finish the streaming context (sends DONE event and updates message)
                                if item_id in item_id_to_streaming_context:
                                    streaming_context = item_id_to_streaming_context[
                                        item_id
                                    ]
                                    await streaming_context.close()
                                    unclosed_item_ids.remove(item_id)

                            elif isinstance(event.data, ResponseCompletedEvent):
                                # All items complete, finish all remaining streaming contexts for this session
                                for item_id in unclosed_item_ids:
                                    streaming_context = item_id_to_streaming_context[
                                        item_id
                                    ]
                                    await streaming_context.close()
                                    unclosed_item_ids.remove(item_id)

                finally:
                    # Cleanup: ensure all streaming contexts for this session are properly finished
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
