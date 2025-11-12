# Standard library imports
from __future__ import annotations

from typing import Any, Literal
from contextlib import AsyncExitStack, asynccontextmanager

from mcp import StdioServerParameters
from agents import Agent, Runner, RunResult, RunResultStreaming
from pydantic import BaseModel
from agents.mcp import MCPServerStdio
from agents.agent import StopAtTools, ToolsToFinalOutputFunction
from agents.guardrail import InputGuardrail, OutputGuardrail
from agents.exceptions import InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered
from openai.types.responses import (
    ResponseCompletedEvent,
    ResponseTextDeltaEvent,
    ResponseFunctionToolCall,
    ResponseFunctionWebSearch,
    ResponseOutputItemDoneEvent,
    ResponseCodeInterpreterToolCall,
    ResponseReasoningSummaryPartDoneEvent,
    ResponseReasoningSummaryPartAddedEvent,
    ResponseReasoningSummaryTextDeltaEvent,
)

# Local imports
from agentex import AsyncAgentex
from agentex.lib.utils import logging
from agentex.lib.utils.mcp import redact_mcp_server_params
from agentex.lib.utils.temporal import heartbeat_if_in_workflow
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.task_message_delta import (
    TextDelta,
    ReasoningSummaryDelta,
)
from agentex.types.task_message_update import (
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
)
from agentex.types.task_message_content import (
    TextContent,
    ReasoningContent,
    ToolRequestContent,
    ToolResponseContent,
)
from agentex.lib.core.services.adk.streaming import (
    StreamingService,
    StreamingTaskMessageContext,
)

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

    def _extract_tool_call_info(self, tool_call_item: Any) -> tuple[str, str, dict[str, Any]]:
        """
        Extract call_id, tool_name, and tool_arguments from a tool call item.

        Args:
            tool_call_item: The tool call item to process

        Returns:
            A tuple of (call_id, tool_name, tool_arguments)
        """
        # Generic handling for different tool call types
        # Try 'call_id' first, then 'id', then generate placeholder
        if hasattr(tool_call_item, "call_id"):
            call_id = tool_call_item.call_id
        elif hasattr(tool_call_item, "id"):
            call_id = tool_call_item.id
        else:
            call_id = f"unknown_call_{id(tool_call_item)}"
            logger.warning(
                f"Warning: Tool call item {type(tool_call_item)} has "
                f"neither 'call_id' nor 'id' attribute, using placeholder: "
                f"{call_id}"
            )

        if isinstance(tool_call_item, ResponseFunctionWebSearch):
            tool_name = "web_search"
            tool_arguments = {"action": tool_call_item.action.model_dump(), "status": tool_call_item.status}
        elif isinstance(tool_call_item, ResponseCodeInterpreterToolCall):
            tool_name = "code_interpreter"
            tool_arguments = {"code": tool_call_item.code, "status": tool_call_item.status}
        else:
            # Generic handling for any tool call type
            tool_name = getattr(tool_call_item, "name", type(tool_call_item).__name__)
            tool_arguments = tool_call_item.model_dump()

        return call_id, tool_name, tool_arguments

    def _extract_tool_response_info(self, tool_call_map: dict[str, Any], tool_output_item: Any) -> tuple[str, str, str]:
        """
        Extract call_id, tool_name, and content from a tool output item.

        Args:
            tool_call_map: Map of call_ids to tool_call items
            tool_output_item: The tool output item to process

        Returns:
            A tuple of (call_id, tool_name, content)
        """
        # Extract call_id and content from the tool_output_item
        # Handle both dictionary access and attribute access
        if hasattr(tool_output_item, "get") and callable(tool_output_item.get):
            # Dictionary-like access
            call_id = tool_output_item["call_id"]
            content = tool_output_item["output"]
        else:
            # Attribute access for structured objects
            call_id = getattr(tool_output_item, "call_id", "")
            content = getattr(tool_output_item, "output", "")

        # Get the name from the tool call map using generic approach
        tool_call = tool_call_map[call_id]
        if hasattr(tool_call, "name"):
            tool_name = tool_call.name
        elif hasattr(tool_call, "type"):
            tool_name = tool_call.type
        else:
            tool_name = type(tool_call).__name__

        return call_id, tool_name, content

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
            Literal["run_llm_again", "stop_on_first_tool"] | StopAtTools | ToolsToFinalOutputFunction
        ) = "run_llm_again",
        mcp_timeout_seconds: int | None = None,
        input_guardrails: list[InputGuardrail] | None = None,
        output_guardrails: list[OutputGuardrail] | None = None,
        max_turns: int | None = None,
        previous_response_id: str | None = None,  # noqa: ARG002
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
            mcp_timeout_seconds: Optional param to set the timeout threshold
                for the MCP servers. Defaults to 5 seconds.
            input_guardrails: Optional list of input guardrails to run on
                initial user input.
            output_guardrails: Optional list of output guardrails to run on
                final agent output.
            mcp_timeout_seconds: Optional param to set the timeout threshold for the MCP servers. Defaults to 5 seconds.
            max_turns: Maximum number of turns the agent can take. Uses Runner's default if None.
        Returns:
            SerializableRunResult: The result of the agent run.
        """
        redacted_params = redact_mcp_server_params(mcp_server_params)

        if self.tracer is None:
            raise RuntimeError("Tracer not initialized - ensure tracer is provided to OpenAIService")
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
                "max_turns": max_turns,
            },
        ) as span:
            heartbeat_if_in_workflow("run agent")

            async with mcp_server_context(mcp_server_params, mcp_timeout_seconds) as servers:
                tools = [
                    tool.to_oai_function_tool() if hasattr(tool, 'to_oai_function_tool') else tool  # type: ignore[attr-defined]
                    for tool in tools
                ] if tools else []
                handoffs = [Agent(**handoff.model_dump()) for handoff in handoffs] if handoffs else []  # type: ignore[misc]

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
                        model_settings.to_oai_model_settings() if hasattr(model_settings, 'to_oai_model_settings')  # type: ignore[attr-defined]
                        else model_settings
                    )
                if input_guardrails is not None:
                    agent_kwargs["input_guardrails"] = input_guardrails
                if output_guardrails is not None:
                    agent_kwargs["output_guardrails"] = output_guardrails

                agent = Agent(**agent_kwargs)

                # Run without streaming
                if max_turns is not None and previous_response_id is not None:
                    result = await Runner.run(
                        starting_agent=agent,
                        input=input_list,
                        max_turns=max_turns,
                        previous_response_id=previous_response_id,
                    )
                elif max_turns is not None:
                    result = await Runner.run(starting_agent=agent, input=input_list, max_turns=max_turns)
                elif previous_response_id is not None:
                    result = await Runner.run(
                        starting_agent=agent, input=input_list, previous_response_id=previous_response_id
                    )
                else:
                    result = await Runner.run(starting_agent=agent, input=input_list)

                if span:
                    span.output = {
                        "new_items": [
                            item.raw_item.model_dump() if isinstance(item.raw_item, BaseModel) else item.raw_item
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
            Literal["run_llm_again", "stop_on_first_tool"] | StopAtTools | ToolsToFinalOutputFunction
        ) = "run_llm_again",
        mcp_timeout_seconds: int | None = None,
        input_guardrails: list[InputGuardrail] | None = None,
        output_guardrails: list[OutputGuardrail] | None = None,
        max_turns: int | None = None,
        previous_response_id: str | None = None,  # noqa: ARG002
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
            input_guardrails: Optional list of input guardrails to run on initial user input.
            output_guardrails: Optional list of output guardrails to run on final agent output.
            max_turns: Maximum number of turns the agent can take. Uses Runner's default if None.
        Returns:
            SerializableRunResult: The result of the agent run.
        """
        if self.streaming_service is None:
            raise ValueError("StreamingService must be available for auto_send methods")
        if self.agentex_client is None:
            raise ValueError("Agentex client must be provided for auto_send methods")

        redacted_params = redact_mcp_server_params(mcp_server_params)

        if self.tracer is None:
            raise RuntimeError("Tracer not initialized - ensure tracer is provided to OpenAIService")
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
                "max_turns": max_turns,
            },
        ) as span:
            heartbeat_if_in_workflow("run agent auto send")

            async with mcp_server_context(mcp_server_params, mcp_timeout_seconds) as servers:
                tools = [
                    tool.to_oai_function_tool() if hasattr(tool, 'to_oai_function_tool') else tool  # type: ignore[attr-defined]
                    for tool in tools
                ] if tools else []
                handoffs = [Agent(**handoff.model_dump()) for handoff in handoffs] if handoffs else []  # type: ignore[misc]
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
                        model_settings.to_oai_model_settings() if hasattr(model_settings, 'to_oai_model_settings')  # type: ignore[attr-defined]
                        else model_settings
                    )
                if input_guardrails is not None:
                    agent_kwargs["input_guardrails"] = input_guardrails
                if output_guardrails is not None:
                    agent_kwargs["output_guardrails"] = output_guardrails

                agent = Agent(**agent_kwargs)

                # Run without streaming
                if max_turns is not None and previous_response_id is not None:
                    result = await Runner.run(
                        starting_agent=agent,
                        input=input_list,
                        max_turns=max_turns,
                        previous_response_id=previous_response_id,
                    )
                elif max_turns is not None:
                    result = await Runner.run(starting_agent=agent, input=input_list, max_turns=max_turns)
                elif previous_response_id is not None:
                    result = await Runner.run(
                        starting_agent=agent, input=input_list, previous_response_id=previous_response_id
                    )
                else:
                    result = await Runner.run(starting_agent=agent, input=input_list)

                if span:
                    span.output = {
                        "new_items": [
                            item.raw_item.model_dump() if isinstance(item.raw_item, BaseModel) else item.raw_item
                            for item in result.new_items
                        ],
                        "final_output": result.final_output,
                    }

                tool_call_map: dict[str, Any] = {}

                for item in result.new_items:
                    if item.type == "message_output_item":
                        text_content = TextContent(
                            author="agent",
                            content=item.raw_item.content[0].text,  # type: ignore[union-attr]
                        )
                        # Create message for the final result using streaming context
                        async with self.streaming_service.streaming_task_message_context(
                            task_id=task_id,
                            initial_content=text_content,
                        ) as streaming_context:
                            await streaming_context.stream_update(
                                update=StreamTaskMessageFull(
                                    parent_task_message=streaming_context.task_message,
                                    content=text_content,
                                    type="full",
                                ),
                            )

                    elif item.type == "tool_call_item":
                        tool_call_item = item.raw_item

                        # Extract tool call information using the helper method
                        call_id, tool_name, tool_arguments = self._extract_tool_call_info(tool_call_item)
                        tool_call_map[call_id] = tool_call_item

                        tool_request_content = ToolRequestContent(
                            author="agent",
                            tool_call_id=call_id,
                            name=tool_name,
                            arguments=tool_arguments,
                        )

                        # Create tool request using streaming context
                        async with self.streaming_service.streaming_task_message_context(
                            task_id=task_id,
                            initial_content=tool_request_content,
                        ) as streaming_context:
                            await streaming_context.stream_update(
                                update=StreamTaskMessageFull(
                                    parent_task_message=streaming_context.task_message,
                                    content=tool_request_content,
                                    type="full",
                                ),
                            )

                    elif item.type == "tool_call_output_item":
                        tool_output_item = item.raw_item

                        # Extract tool response information using the helper method
                        call_id, tool_name, content = self._extract_tool_response_info(tool_call_map, tool_output_item)

                        tool_response_content = ToolResponseContent(
                            author="agent",
                            tool_call_id=call_id,
                            name=tool_name,
                            content=content,
                        )
                        # Create tool response using streaming context
                        async with self.streaming_service.streaming_task_message_context(
                            task_id=task_id, initial_content=tool_response_content
                        ) as streaming_context:
                            await streaming_context.stream_update(
                                update=StreamTaskMessageFull(
                                    parent_task_message=streaming_context.task_message,
                                    content=tool_response_content,
                                    type="full",
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
            Literal["run_llm_again", "stop_on_first_tool"] | StopAtTools | ToolsToFinalOutputFunction
        ) = "run_llm_again",
        mcp_timeout_seconds: int | None = None,
        input_guardrails: list[InputGuardrail] | None = None,
        output_guardrails: list[OutputGuardrail] | None = None,
        max_turns: int | None = None,
        previous_response_id: str | None = None,  # noqa: ARG002
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
            mcp_timeout_seconds: Optional param to set the timeout threshold
                for the MCP servers. Defaults to 5 seconds.
            input_guardrails: Optional list of input guardrails to run on
                initial user input.
            output_guardrails: Optional list of output guardrails to run on
                final agent output.
            mcp_timeout_seconds: Optional param to set the timeout threshold for the MCP servers. Defaults to 5 seconds.
            max_turns: Maximum number of turns the agent can take. Uses Runner's default if None.
        Returns:
            RunResultStreaming: The result of the agent run with streaming.
        """
        if self.tracer is None:
            raise RuntimeError("Tracer not initialized - ensure tracer is provided to OpenAIService")
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
                "max_turns": max_turns,
            },
        ) as span:
            heartbeat_if_in_workflow("run agent streamed")

            async with mcp_server_context(mcp_server_params, mcp_timeout_seconds) as servers:
                tools = [
                    tool.to_oai_function_tool() if hasattr(tool, 'to_oai_function_tool') else tool  # type: ignore[attr-defined]
                    for tool in tools
                ] if tools else []
                handoffs = [Agent(**handoff.model_dump()) for handoff in handoffs] if handoffs else []  # type: ignore[misc]
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
                        model_settings.to_oai_model_settings() if hasattr(model_settings, 'to_oai_model_settings')  # type: ignore[attr-defined]
                        else model_settings
                    )
                if input_guardrails is not None:
                    agent_kwargs["input_guardrails"] = input_guardrails
                if output_guardrails is not None:
                    agent_kwargs["output_guardrails"] = output_guardrails

                agent = Agent(**agent_kwargs)

                # Run with streaming (but no TaskMessage creation)
                if max_turns is not None and previous_response_id is not None:
                    result = Runner.run_streamed(
                        starting_agent=agent,
                        input=input_list,
                        max_turns=max_turns,
                        previous_response_id=previous_response_id,
                    )
                elif max_turns is not None:
                    result = Runner.run_streamed(starting_agent=agent, input=input_list, max_turns=max_turns)
                elif previous_response_id is not None:
                    result = Runner.run_streamed(
                        starting_agent=agent, input=input_list, previous_response_id=previous_response_id
                    )
                else:
                    result = Runner.run_streamed(starting_agent=agent, input=input_list)

                if span:
                    span.output = {
                        "new_items": [
                            item.raw_item.model_dump() if isinstance(item.raw_item, BaseModel) else item.raw_item
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
            Literal["run_llm_again", "stop_on_first_tool"] | StopAtTools | ToolsToFinalOutputFunction
        ) = "run_llm_again",
        mcp_timeout_seconds: int | None = None,
        input_guardrails: list[InputGuardrail] | None = None,
        output_guardrails: list[OutputGuardrail] | None = None,
        max_turns: int | None = None,
        previous_response_id: str | None = None,  # noqa: ARG002
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
            mcp_timeout_seconds: Optional param to set the timeout threshold
                for the MCP servers. Defaults to 5 seconds.
            input_guardrails: Optional list of input guardrails to run on
                initial user input.
            output_guardrails: Optional list of output guardrails to run on
                final agent output.
            mcp_timeout_seconds: Optional param to set the timeout threshold for the MCP servers. Defaults to 5 seconds.
            max_turns: Maximum number of turns the agent can take. Uses Runner's default if None.

        Returns:
            RunResultStreaming: The result of the agent run with streaming.
        """
        if self.streaming_service is None:
            raise ValueError("StreamingService must be available for auto_send methods")
        if self.agentex_client is None:
            raise ValueError("Agentex client must be provided for auto_send methods")

        tool_call_map: dict[str, ResponseFunctionToolCall] = {}

        if self.tracer is None:
            raise RuntimeError("Tracer not initialized - ensure tracer is provided to OpenAIService")
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
                "max_turns": max_turns,
            },
        ) as span:
            heartbeat_if_in_workflow("run agent streamed auto send")

            async with mcp_server_context(mcp_server_params, mcp_timeout_seconds) as servers:
                tools = [
                    tool.to_oai_function_tool() if hasattr(tool, 'to_oai_function_tool') else tool  # type: ignore[attr-defined]
                    for tool in tools
                ] if tools else []
                handoffs = [Agent(**handoff.model_dump()) for handoff in handoffs] if handoffs else []  # type: ignore[misc]
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
                        model_settings.to_oai_model_settings() if hasattr(model_settings, 'to_oai_model_settings')  # type: ignore[attr-defined]
                        else model_settings
                    )
                if input_guardrails is not None:
                    agent_kwargs["input_guardrails"] = input_guardrails
                if output_guardrails is not None:
                    agent_kwargs["output_guardrails"] = output_guardrails

                agent = Agent(**agent_kwargs)

                # Run with streaming
                if max_turns is not None:
                    result = Runner.run_streamed(starting_agent=agent, input=input_list, max_turns=max_turns)
                else:
                    result = Runner.run_streamed(starting_agent=agent, input=input_list)

                item_id_to_streaming_context: dict[str, StreamingTaskMessageContext] = {}
                unclosed_item_ids: set[str] = set()
                # Simple string to accumulate reasoning summary
                current_reasoning_summary: str = ""

                try:
                    # Process streaming events with TaskMessage creation
                    async for event in result.stream_events():
                        heartbeat_if_in_workflow("processing stream event with auto send")

                        if event.type == "run_item_stream_event":
                            if event.item.type == "tool_call_item":
                                tool_call_item = event.item.raw_item

                                # Extract tool call information using the helper method
                                call_id, tool_name, tool_arguments = self._extract_tool_call_info(tool_call_item)
                                tool_call_map[call_id] = tool_call_item

                                tool_request_content = ToolRequestContent(
                                    author="agent",
                                    tool_call_id=call_id,
                                    name=tool_name,
                                    arguments=tool_arguments,
                                )

                                # Create tool request using streaming context (immediate completion)
                                async with self.streaming_service.streaming_task_message_context(
                                    task_id=task_id,
                                    initial_content=tool_request_content,
                                ) as streaming_context:
                                    # The message has already been persisted, but we still need to send an upda
                                    await streaming_context.stream_update(
                                        update=StreamTaskMessageFull(
                                            parent_task_message=streaming_context.task_message,
                                            content=tool_request_content,
                                            type="full",
                                        ),
                                    )

                            elif event.item.type == "tool_call_output_item":
                                tool_output_item = event.item.raw_item

                                # Extract tool response information using the helper method
                                call_id, tool_name, content = self._extract_tool_response_info(
                                    tool_call_map, tool_output_item
                                )

                                tool_response_content = ToolResponseContent(
                                    author="agent",
                                    tool_call_id=call_id,
                                    name=tool_name,
                                    content=content,
                                )

                                # Create tool response using streaming context (immediate completion)
                                async with self.streaming_service.streaming_task_message_context(
                                    task_id=task_id, initial_content=tool_response_content
                                ) as streaming_context:
                                    # The message has already been persisted, but we still need to send an update
                                    await streaming_context.stream_update(
                                        update=StreamTaskMessageFull(
                                            parent_task_message=streaming_context.task_message,
                                            content=tool_response_content,
                                            type="full",
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
                                    item_id_to_streaming_context[item_id] = await streaming_context.open()
                                    unclosed_item_ids.add(item_id)
                                else:
                                    streaming_context = item_id_to_streaming_context[item_id]

                                # Stream the delta through the streaming service
                                await streaming_context.stream_update(
                                    update=StreamTaskMessageDelta(
                                        parent_task_message=streaming_context.task_message,
                                        delta=TextDelta(text_delta=event.data.delta, type="text"),
                                        type="delta",
                                    ),
                                )
                            # Reasoning step one: new summary part added
                            elif isinstance(event.data, ResponseReasoningSummaryPartAddedEvent):
                                # We need to create a new streaming context for this reasoning item
                                item_id = event.data.item_id
                                
                                # Reset the reasoning summary string
                                current_reasoning_summary = ""
                                
                                streaming_context = self.streaming_service.streaming_task_message_context(
                                    task_id=task_id,
                                    initial_content=ReasoningContent(
                                        author="agent",
                                        summary=[],
                                        content=[],
                                        type="reasoning",
                                        style="active",
                                    ),
                                )

                                # Replace the existing streaming context (if it exists)
                                # Why do we replace? Cause all the reasoning parts use the same item_id!
                                item_id_to_streaming_context[item_id] = await streaming_context.open()
                                unclosed_item_ids.add(item_id)
                            
                            # Reasoning step two: handling summary text delta
                            elif isinstance(event.data, ResponseReasoningSummaryTextDeltaEvent):
                                # Accumulate the delta into the string
                                current_reasoning_summary += event.data.delta
                                streaming_context = item_id_to_streaming_context[item_id]

                                # Stream the summary delta through the streaming service
                                await streaming_context.stream_update(
                                    update=StreamTaskMessageDelta(
                                        parent_task_message=streaming_context.task_message,
                                        delta=ReasoningSummaryDelta(
                                            summary_index=event.data.summary_index,
                                            summary_delta=event.data.delta,
                                            type="reasoning_summary",
                                        ),
                                        type="delta",
                                    ),
                                )

                            # Reasoning step three: handling summary text done, closing the streaming context
                            elif isinstance(event.data, ResponseReasoningSummaryPartDoneEvent):
                                # Handle reasoning summary text completion
                                streaming_context = item_id_to_streaming_context[item_id]
                                
                                # Create the complete reasoning content with the accumulated summary
                                complete_reasoning_content = ReasoningContent(
                                    author="agent",
                                    summary=[current_reasoning_summary],
                                    content=[],
                                    type="reasoning",
                                    style="static",
                                )
                                
                                # Send a full message update with the complete reasoning content
                                await streaming_context.stream_update(
                                    update=StreamTaskMessageFull(
                                        parent_task_message=streaming_context.task_message,
                                        content=complete_reasoning_content,
                                        type="full",
                                    ),
                                )
                                
                                await streaming_context.close()
                                unclosed_item_ids.discard(item_id)
                                

                            elif isinstance(event.data, ResponseOutputItemDoneEvent):
                                # Handle item completion
                                item_id = event.data.item.id

                                # Finish the streaming context (sends DONE event and updates message)
                                if item_id in item_id_to_streaming_context:
                                    streaming_context = item_id_to_streaming_context[item_id]
                                    await streaming_context.close()
                                    if item_id in unclosed_item_ids:
                                        unclosed_item_ids.remove(item_id)

                            elif isinstance(event.data, ResponseCompletedEvent):
                                # All items complete, finish all remaining streaming contexts for this session
                                # Create a copy to avoid modifying set during iteration
                                remaining_items = list(unclosed_item_ids)
                                for item_id in remaining_items:
                                    if (
                                        item_id in unclosed_item_ids and item_id in item_id_to_streaming_context
                                    ):  # Check if still unclosed
                                        streaming_context = item_id_to_streaming_context[item_id]
                                        await streaming_context.close()
                                        unclosed_item_ids.discard(item_id)

                except InputGuardrailTripwireTriggered as e:
                    # Handle guardrail trigger by sending a rejection message
                    rejection_message = "I'm sorry, but I cannot process this request due to a guardrail. Please try a different question."

                    # Try to extract rejection message from the guardrail result
                    if hasattr(e, "guardrail_result") and hasattr(e.guardrail_result, "output"):
                        output_info = getattr(e.guardrail_result.output, "output_info", {})
                        if isinstance(output_info, dict) and "rejection_message" in output_info:
                            rejection_message = output_info["rejection_message"]
                        elif hasattr(e.guardrail_result, "guardrail"):
                            # Fall back to using guardrail name if no custom message
                            triggered_guardrail_name = getattr(e.guardrail_result.guardrail, "name", None)
                            if triggered_guardrail_name:
                                rejection_message = f"I'm sorry, but I cannot process this request. The '{triggered_guardrail_name}' guardrail was triggered."

                    # Create and send the rejection message as a TaskMessage
                    async with self.streaming_service.streaming_task_message_context(
                        task_id=task_id,
                        initial_content=TextContent(
                            author="agent",
                            content=rejection_message,
                        ),
                    ) as streaming_context:
                        # Send the full message
                        await streaming_context.stream_update(
                            update=StreamTaskMessageFull(
                                parent_task_message=streaming_context.task_message,
                                content=TextContent(
                                    author="agent",
                                    content=rejection_message,
                                ),
                                type="full",
                            ),
                        )

                    # Re-raise to let the activity handle it
                    raise

                except OutputGuardrailTripwireTriggered as e:
                    # Handle output guardrail trigger by sending a rejection message
                    rejection_message = "I'm sorry, but I cannot provide this response due to a guardrail. Please try a different question."

                    # Try to extract rejection message from the guardrail result
                    if hasattr(e, "guardrail_result") and hasattr(e.guardrail_result, "output"):
                        output_info = getattr(e.guardrail_result.output, "output_info", {})
                        if isinstance(output_info, dict) and "rejection_message" in output_info:
                            rejection_message = output_info["rejection_message"]
                        elif hasattr(e.guardrail_result, "guardrail"):
                            # Fall back to using guardrail name if no custom message
                            triggered_guardrail_name = getattr(e.guardrail_result.guardrail, "name", None)
                            if triggered_guardrail_name:
                                rejection_message = f"I'm sorry, but I cannot provide this response. The '{triggered_guardrail_name}' guardrail was triggered."

                    # Create and send the rejection message as a TaskMessage
                    async with self.streaming_service.streaming_task_message_context(
                        task_id=task_id,
                        initial_content=TextContent(
                            author="agent",
                            content=rejection_message,
                        ),
                    ) as streaming_context:
                        # Send the full message
                        await streaming_context.stream_update(
                            update=StreamTaskMessageFull(
                                parent_task_message=streaming_context.task_message,
                                content=TextContent(
                                    author="agent",
                                    content=rejection_message,
                                ),
                                type="full",
                            ),
                        )

                    # Re-raise to let the activity handle it
                    raise

                finally:
                    # Cleanup: ensure all streaming contexts for this session are properly finished
                    # Create a copy to avoid modifying set during iteration
                    remaining_items = list(unclosed_item_ids)
                    for item_id in remaining_items:
                        if (
                            item_id in unclosed_item_ids and item_id in item_id_to_streaming_context
                        ):  # Check if still unclosed
                            streaming_context = item_id_to_streaming_context[item_id]
                            await streaming_context.close()
                            unclosed_item_ids.discard(item_id)

                if span:
                    span.output = {
                        "new_items": [
                            item.raw_item.model_dump() if isinstance(item.raw_item, BaseModel) else item.raw_item
                            for item in result.new_items
                        ],
                        "final_output": result.final_output,
                    }

        return result
