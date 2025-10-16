from typing import Any, Literal
from datetime import timedelta

from mcp import StdioServerParameters
from agents import Agent, RunResult, RunResultStreaming
from agents.tool import Tool
from agents.agent import StopAtTools, ToolsToFinalOutputFunction
from agents.guardrail import InputGuardrail, OutputGuardrail
from temporalio.common import RetryPolicy
from agents.agent_output import AgentOutputSchemaBase
from agents.model_settings import ModelSettings

from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import in_temporal_workflow
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.lib.types.agent_results import (
    SerializableRunResult,
    SerializableRunResultStreaming,
)
from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.services.adk.streaming import StreamingService
from agentex.lib.core.services.adk.providers.openai import OpenAIService
from agentex.lib.core.adapters.streams.adapter_redis import RedisStreamRepository
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.temporal.activities.adk.providers.openai_activities import (
    RunAgentParams,
    OpenAIActivityName,
    RunAgentAutoSendParams,
    RunAgentStreamedAutoSendParams,
)

logger = make_logger(__name__)

# Default retry policy for all OpenAI operations
DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


class OpenAIModule:
    """
    Module for managing OpenAI agent operations in Agentex.
    Provides high-level methods for running agents with and without streaming.
    """

    def __init__(
        self,
        openai_service: OpenAIService | None = None,
    ):
        if openai_service is None:
            # Create default service
            agentex_client = create_async_agentex_client()
            stream_repository = RedisStreamRepository()
            streaming_service = StreamingService(
                agentex_client=agentex_client,
                stream_repository=stream_repository,
            )
            tracer = AsyncTracer(agentex_client)
            self._openai_service = OpenAIService(
                agentex_client=agentex_client,
                streaming_service=streaming_service,
                tracer=tracer,
            )
        else:
            self._openai_service = openai_service

    async def run_agent(
        self,
        input_list: list[dict[str, Any]],
        mcp_server_params: list[StdioServerParameters],
        agent_name: str,
        agent_instructions: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=600),
        heartbeat_timeout: timedelta = timedelta(seconds=600),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
        handoff_description: str | None = None,
        handoffs: list[Agent] | None = None,
        model: str | None = None,
        model_settings: ModelSettings | None = None,
        tools: list[Tool] | None = None,
        output_type: type[Any] | AgentOutputSchemaBase | None = None,
        tool_use_behavior: (
            Literal["run_llm_again", "stop_on_first_tool"] | StopAtTools | ToolsToFinalOutputFunction
        ) = "run_llm_again",
        mcp_timeout_seconds: int | None = None,
        input_guardrails: list[InputGuardrail] | None = None,
        output_guardrails: list[OutputGuardrail] | None = None,
        max_turns: int | None = None,
        previous_response_id: str | None = None,
    ) -> SerializableRunResult | RunResult:
        """
        Run an agent without streaming or TaskMessage creation.

        DEFAULT: No TaskMessage creation, returns only the result.

        Args:
            input_list: List of input data for the agent.
            mcp_server_params: MCP server parameters for the agent.
            agent_name: The name of the agent to run.
            agent_instructions: Instructions for the agent.
            trace_id: Optional trace ID for tracing.
            parent_span_id: Optional parent span for tracing.
            start_to_close_timeout: Maximum time allowed for the operation.
            heartbeat_timeout: Maximum time between heartbeats.
            retry_policy: Policy for retrying failed operations.
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
            previous_response_id: Optional previous response ID for conversation continuity.

        Returns:
            Union[SerializableRunResult, RunResult]: SerializableRunResult when in Temporal, RunResult otherwise.
        """
        if in_temporal_workflow():
            params = RunAgentParams(
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                input_list=input_list,
                mcp_server_params=mcp_server_params,
                agent_name=agent_name,
                agent_instructions=agent_instructions,
                handoff_description=handoff_description,
                handoffs=handoffs,  # type: ignore[arg-type]
                model=model,
                model_settings=model_settings,  # type: ignore[arg-type]
                tools=tools,  # type: ignore[arg-type]
                output_type=output_type,
                tool_use_behavior=tool_use_behavior,  # type: ignore[arg-type]
                mcp_timeout_seconds=mcp_timeout_seconds,
                input_guardrails=input_guardrails,  # type: ignore[arg-type]
                output_guardrails=output_guardrails,  # type: ignore[arg-type]
                max_turns=max_turns,
                previous_response_id=previous_response_id,
            )
            return await ActivityHelpers.execute_activity(
                activity_name=OpenAIActivityName.RUN_AGENT,
                request=params,
                response_type=SerializableRunResult,
                start_to_close_timeout=start_to_close_timeout,
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )
        else:
            return await self._openai_service.run_agent(
                input_list=input_list,
                mcp_server_params=mcp_server_params,
                agent_name=agent_name,
                agent_instructions=agent_instructions,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                handoff_description=handoff_description,
                handoffs=handoffs,
                model=model,
                model_settings=model_settings,
                tools=tools,
                output_type=output_type,
                tool_use_behavior=tool_use_behavior,
                mcp_timeout_seconds=mcp_timeout_seconds,
                input_guardrails=input_guardrails,
                output_guardrails=output_guardrails,
                max_turns=max_turns,
                previous_response_id=previous_response_id,
            )

    async def run_agent_auto_send(
        self,
        task_id: str,
        input_list: list[dict[str, Any]],
        mcp_server_params: list[StdioServerParameters],
        agent_name: str,
        agent_instructions: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=600),
        heartbeat_timeout: timedelta = timedelta(seconds=600),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
        handoff_description: str | None = None,
        handoffs: list[Agent] | None = None,
        model: str | None = None,
        model_settings: ModelSettings | None = None,
        tools: list[Tool] | None = None,
        output_type: type[Any] | AgentOutputSchemaBase | None = None,
        tool_use_behavior: (
            Literal["run_llm_again", "stop_on_first_tool"] | StopAtTools | ToolsToFinalOutputFunction
        ) = "run_llm_again",
        mcp_timeout_seconds: int | None = None,
        input_guardrails: list[InputGuardrail] | None = None,
        output_guardrails: list[OutputGuardrail] | None = None,
        max_turns: int | None = None,
        previous_response_id: str | None = None,
    ) -> SerializableRunResult | RunResult:
        """
        Run an agent with automatic TaskMessage creation.

        Args:
            task_id: The ID of the task to run the agent for.
            input_list: List of input data for the agent.
            mcp_server_params: MCP server parameters for the agent.
            agent_name: The name of the agent to run.
            agent_instructions: Instructions for the agent.
            trace_id: Optional trace ID for tracing.
            parent_span_id: Optional parent span for tracing.
            start_to_close_timeout: Maximum time allowed for the operation.
            heartbeat_timeout: Maximum time between heartbeats.
            retry_policy: Policy for retrying failed operations.
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
            previous_response_id: Optional previous response ID for conversation continuity.

        Returns:
            Union[SerializableRunResult, RunResult]: SerializableRunResult when in Temporal, RunResult otherwise.
        """
        if in_temporal_workflow():
            params = RunAgentAutoSendParams(
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                task_id=task_id,
                input_list=input_list,
                mcp_server_params=mcp_server_params,
                agent_name=agent_name,
                agent_instructions=agent_instructions,
                handoff_description=handoff_description,
                handoffs=handoffs,  # type: ignore[arg-type]
                model=model,
                model_settings=model_settings,  # type: ignore[arg-type]
                tools=tools,  # type: ignore[arg-type]
                output_type=output_type,
                tool_use_behavior=tool_use_behavior,  # type: ignore[arg-type]
                mcp_timeout_seconds=mcp_timeout_seconds,
                input_guardrails=input_guardrails,  # type: ignore[arg-type]
                output_guardrails=output_guardrails,  # type: ignore[arg-type]
                max_turns=max_turns,
                previous_response_id=previous_response_id,
            )
            return await ActivityHelpers.execute_activity(
                activity_name=OpenAIActivityName.RUN_AGENT_AUTO_SEND,
                request=params,
                response_type=SerializableRunResult,
                start_to_close_timeout=start_to_close_timeout,
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )
        else:
            return await self._openai_service.run_agent_auto_send(
                task_id=task_id,
                input_list=input_list,
                mcp_server_params=mcp_server_params,
                agent_name=agent_name,
                agent_instructions=agent_instructions,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                handoff_description=handoff_description,
                handoffs=handoffs,
                model=model,
                model_settings=model_settings,
                tools=tools,
                output_type=output_type,
                tool_use_behavior=tool_use_behavior,
                mcp_timeout_seconds=mcp_timeout_seconds,
                input_guardrails=input_guardrails,
                output_guardrails=output_guardrails,
                max_turns=max_turns,
                previous_response_id=previous_response_id,
            )

    async def run_agent_streamed(
        self,
        input_list: list[dict[str, Any]],
        mcp_server_params: list[StdioServerParameters],
        agent_name: str,
        agent_instructions: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        handoff_description: str | None = None,
        handoffs: list[Agent] | None = None,
        model: str | None = None,
        model_settings: ModelSettings | None = None,
        tools: list[Tool] | None = None,
        output_type: type[Any] | AgentOutputSchemaBase | None = None,
        tool_use_behavior: (
            Literal["run_llm_again", "stop_on_first_tool"] | StopAtTools | ToolsToFinalOutputFunction
        ) = "run_llm_again",
        mcp_timeout_seconds: int | None = None,
        input_guardrails: list[InputGuardrail] | None = None,
        output_guardrails: list[OutputGuardrail] | None = None,
        max_turns: int | None = None,
        previous_response_id: str | None = None,
    ) -> RunResultStreaming:
        """
        Run an agent with streaming enabled but no TaskMessage creation.

        DEFAULT: No TaskMessage creation, returns only the result.

        NOTE: This method does NOT work in Temporal workflows!
        Use run_agent_streamed_auto_send() instead for Temporal workflows.

        Args:
            input_list: List of input data for the agent.
            mcp_server_params: MCP server parameters for the agent.
            agent_name: The name of the agent to run.
            agent_instructions: Instructions for the agent.
            trace_id: Optional trace ID for tracing.
            parent_span_id: Optional parent span for tracing.
            start_to_close_timeout: Maximum time allowed for the operation.
            heartbeat_timeout: Maximum time between heartbeats.
            retry_policy: Policy for retrying failed operations.
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
            previous_response_id: Optional previous response ID for conversation continuity.

        Returns:
            RunResultStreaming: The result of the agent run with streaming.

        Raises:
            ValueError: If called from within a Temporal workflow
        """
        # Temporal workflows should use the auto_send variant
        if in_temporal_workflow():
            raise ValueError(
                "run_agent_streamed() cannot be used in Temporal workflows. "
                "Use run_agent_streamed_auto_send() instead, which properly handles "
                "TaskMessage creation and streaming through the streaming service."
            )

        return await self._openai_service.run_agent_streamed(
            input_list=input_list,
            mcp_server_params=mcp_server_params,
            agent_name=agent_name,
            agent_instructions=agent_instructions,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            handoff_description=handoff_description,
            handoffs=handoffs,
            model=model,
            model_settings=model_settings,
            tools=tools,
            output_type=output_type,
            tool_use_behavior=tool_use_behavior,
            mcp_timeout_seconds=mcp_timeout_seconds,
            input_guardrails=input_guardrails,
            output_guardrails=output_guardrails,
            max_turns=max_turns,
            previous_response_id=previous_response_id,
        )

    async def run_agent_streamed_auto_send(
        self,
        task_id: str,
        input_list: list[dict[str, Any]],
        mcp_server_params: list[StdioServerParameters],
        agent_name: str,
        agent_instructions: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=600),
        heartbeat_timeout: timedelta = timedelta(seconds=600),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
        handoff_description: str | None = None,
        handoffs: list[Agent] | None = None,
        model: str | None = None,
        model_settings: ModelSettings | None = None,
        tools: list[Tool] | None = None,
        output_type: type[Any] | AgentOutputSchemaBase | None = None,
        tool_use_behavior: (
            Literal["run_llm_again", "stop_on_first_tool"] | StopAtTools | ToolsToFinalOutputFunction
        ) = "run_llm_again",
        mcp_timeout_seconds: int | None = None,
        input_guardrails: list[InputGuardrail] | None = None,
        output_guardrails: list[OutputGuardrail] | None = None,
        max_turns: int | None = None,
        previous_response_id: str | None = None,
    ) -> SerializableRunResultStreaming | RunResultStreaming:
        """
        Run an agent with streaming enabled and automatic TaskMessage creation.

        Args:
            task_id: The ID of the task to run the agent for.
            input_list: List of input data for the agent.
            mcp_server_params: MCP server parameters for the agent.
            agent_name: The name of the agent to run.
            agent_instructions: Instructions for the agent.
            trace_id: Optional trace ID for tracing.
            parent_span_id: Optional parent span for tracing.
            start_to_close_timeout: Maximum time allowed for the operation.
            heartbeat_timeout: Maximum time between heartbeats.
            retry_policy: Policy for retrying failed operations.
            handoff_description: Optional description of the handoff.
            handoffs: Optional list of handoffs.
            model: Optional model to use.
            model_settings: Optional model settings.
            tools: Optional list of tools.
            input_guardrails: Optional list of input guardrails to run on initial user input.
            output_guardrails: Optional list of output guardrails to run on final agent output.
            output_type: Optional output type.
            tool_use_behavior: Optional tool use behavior.
            mcp_timeout_seconds: Optional param to set the timeout threshold for the MCP servers. Defaults to 5 seconds.
            max_turns: Maximum number of turns the agent can take. Uses Runner's default if None.
            previous_response_id: Optional previous response ID for conversation continuity.

        Returns:
            Union[SerializableRunResultStreaming, RunResultStreaming]: SerializableRunResultStreaming when in Temporal, RunResultStreaming otherwise.
        """
        if in_temporal_workflow():
            params = RunAgentStreamedAutoSendParams(
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                task_id=task_id,
                input_list=input_list,
                mcp_server_params=mcp_server_params,
                agent_name=agent_name,
                agent_instructions=agent_instructions,
                handoff_description=handoff_description,
                handoffs=handoffs,
                model=model,
                model_settings=model_settings,
                tools=tools,
                output_type=output_type,
                tool_use_behavior=tool_use_behavior,
                mcp_timeout_seconds=mcp_timeout_seconds,
                input_guardrails=input_guardrails,
                output_guardrails=output_guardrails,
                max_turns=max_turns,
            )
            return await ActivityHelpers.execute_activity(
                activity_name=OpenAIActivityName.RUN_AGENT_STREAMED_AUTO_SEND,
                request=params,
                response_type=SerializableRunResultStreaming,
                start_to_close_timeout=start_to_close_timeout,
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )
        else:
            return await self._openai_service.run_agent_streamed_auto_send(
                task_id=task_id,
                input_list=input_list,
                mcp_server_params=mcp_server_params,
                agent_name=agent_name,
                agent_instructions=agent_instructions,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                handoff_description=handoff_description,
                handoffs=handoffs,
                model=model,
                model_settings=model_settings,
                tools=tools,
                output_type=output_type,
                tool_use_behavior=tool_use_behavior,
                mcp_timeout_seconds=mcp_timeout_seconds,
                input_guardrails=input_guardrails,
                output_guardrails=output_guardrails,
                max_turns=max_turns,
                previous_response_id=previous_response_id,
            )

    async def run(
        self,
        agent: Agent,
        input: str | list[dict[str, Any]],
        task_id: str,
        *,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=600),
        heartbeat_timeout: timedelta = timedelta(seconds=600),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
        max_turns: int | None = None,
        mcp_server_params: list[StdioServerParameters] | None = None,
        previous_response_id: str | None = None,
    ) -> SerializableRunResultStreaming | RunResultStreaming:
        """
        Run an OpenAI Agent with automatic streaming to AgentEx UI.

        This is a simple wrapper that lets you use standard OpenAI Agents SDK
        patterns while getting AgentEx features (streaming, tracing, TaskMessages).

        Works everywhere: Temporal workflows, sync agents (FastACP), standalone scripts.

        Example:
            from agents import Agent, function_tool, ModelSettings
            from openai.types.shared import Reasoning

            @function_tool
            def get_weather(city: str) -> str:
                return f"Weather in {city}: Sunny"

            agent = Agent(
                name="Weather Bot",
                instructions="Help with weather",
                model="gpt-4o",
                model_settings=ModelSettings(
                    parallel_tool_calls=True,
                    reasoning=Reasoning(effort="low", summary="auto")
                ),
                tools=[get_weather]
            )

            result = await adk.providers.openai.run(
                agent=agent,
                input="What's the weather in Tokyo?",
                task_id=params.task.id,
                trace_id=params.task.id,
                parent_span_id=span.id,
            )

        Args:
            agent: Standard OpenAI Agents SDK Agent object
            input: User message (str) or conversation history (list of dicts)
            task_id: AgentEx task ID for streaming
            trace_id: Optional trace ID (defaults to task_id)
            parent_span_id: Optional parent span for nested tracing
            start_to_close_timeout: Maximum time allowed for the operation
            heartbeat_timeout: Maximum time between heartbeats
            retry_policy: Policy for retrying failed operations
            max_turns: Max conversation turns (default from Runner)
            mcp_server_params: Optional MCP server configurations
            previous_response_id: For conversation continuity

        Returns:
            RunResult with final_output and conversation history
        """
        # 1. Normalize input format
        if isinstance(input, str):
            input_list = [{"role": "user", "content": input}]
        else:
            input_list = input

        # 2. Extract agent properties
        agent_name = agent.name
        agent_instructions = agent.instructions

        # Extract model name
        if isinstance(agent.model, str):
            model = agent.model
        else:
            model = None  # Will use default

        # Extract model settings and convert to serializable format if needed
        model_settings = getattr(agent, 'model_settings', None)
        if model_settings and not isinstance(model_settings, dict):
            # Convert OpenAI SDK ModelSettings to serializable format
            from agentex.lib.core.temporal.activities.adk.providers.openai_activities import ModelSettings as SerializableModelSettings

            model_settings = SerializableModelSettings(
                temperature=getattr(model_settings, 'temperature', None),
                max_tokens=getattr(model_settings, 'max_tokens', None),
                top_p=getattr(model_settings, 'top_p', None),
                frequency_penalty=getattr(model_settings, 'frequency_penalty', None),
                presence_penalty=getattr(model_settings, 'presence_penalty', None),
                parallel_tool_calls=getattr(model_settings, 'parallel_tool_calls', None),
                tool_choice=getattr(model_settings, 'tool_choice', None),
                reasoning=getattr(model_settings, 'reasoning', None),
                store=getattr(model_settings, 'store', None),
                metadata=getattr(model_settings, 'metadata', None),
                extra_headers=getattr(model_settings, 'extra_headers', None),
                extra_body=getattr(model_settings, 'extra_body', None),
                extra_args=getattr(model_settings, 'extra_args', None),
            )

        # Extract other properties and convert tools to serializable format
        tools = agent.tools or []
        if tools:
            # Import all tool types we need
            from agents.tool import (
                FunctionTool as OAIFunctionTool,
                WebSearchTool as OAIWebSearchTool,
                FileSearchTool as OAIFileSearchTool,
                ComputerTool as OAIComputerTool,
                LocalShellTool as OAILocalShellTool,
                CodeInterpreterTool as OAICodeInterpreterTool,
                ImageGenerationTool as OAIImageGenerationTool,
            )
            from agentex.lib.core.temporal.activities.adk.providers.openai_activities import (
                FunctionTool as SerializableFunctionTool,
                WebSearchTool as SerializableWebSearchTool,
                FileSearchTool as SerializableFileSearchTool,
                ComputerTool as SerializableComputerTool,
                LocalShellTool as SerializableLocalShellTool,
                CodeInterpreterTool as SerializableCodeInterpreterTool,
                ImageGenerationTool as SerializableImageGenerationTool,
            )

            # Convert tools to ensure they're serializable for Temporal
            converted_tools = []
            for tool in tools:
                # If already a serializable wrapper, keep as-is
                if hasattr(tool, 'to_oai_function_tool'):
                    converted_tools.append(tool)
                # Convert OpenAI SDK tool types to serializable wrappers
                elif isinstance(tool, OAIFunctionTool):
                    # FunctionTool requires on_invoke_tool callable
                    if not hasattr(tool, 'on_invoke_tool') or tool.on_invoke_tool is None:
                        raise ValueError(f"FunctionTool '{tool.name}' missing required on_invoke_tool callable")
                    converted_tools.append(SerializableFunctionTool(
                        name=tool.name,
                        description=tool.description,
                        params_json_schema=tool.params_json_schema,
                        strict_json_schema=getattr(tool, 'strict_json_schema', True),
                        on_invoke_tool=tool.on_invoke_tool,
                    ))
                elif isinstance(tool, OAIWebSearchTool):
                    converted_tools.append(SerializableWebSearchTool(
                        user_location=getattr(tool, 'user_location', None),
                        search_context_size=getattr(tool, 'search_context_size', 'medium'),
                    ))
                elif isinstance(tool, OAIFileSearchTool):
                    converted_tools.append(SerializableFileSearchTool(
                        vector_store_ids=tool.vector_store_ids,
                        max_num_results=getattr(tool, 'max_num_results', None),
                        include_search_results=getattr(tool, 'include_search_results', False),
                        ranking_options=getattr(tool, 'ranking_options', None),
                        filters=getattr(tool, 'filters', None),
                    ))
                elif isinstance(tool, OAIComputerTool):
                    converted_tools.append(SerializableComputerTool(
                        computer=getattr(tool, 'computer', None),
                        on_safety_check=getattr(tool, 'on_safety_check', None),
                    ))
                elif isinstance(tool, OAILocalShellTool):
                    converted_tools.append(SerializableLocalShellTool(
                        executor=getattr(tool, 'executor', None),
                    ))
                elif isinstance(tool, OAICodeInterpreterTool):
                    converted_tools.append(SerializableCodeInterpreterTool(
                        tool_config=getattr(tool, 'tool_config', {"type": "code_interpreter"}),
                    ))
                elif isinstance(tool, OAIImageGenerationTool):
                    converted_tools.append(SerializableImageGenerationTool(
                        tool_config=getattr(tool, 'tool_config', {"type": "image_generation"}),
                    ))
                else:
                    # Unknown tool type - keep as-is and let downstream handle it
                    converted_tools.append(tool)
            tools = converted_tools

        handoffs = agent.handoffs or []
        handoff_description = getattr(agent, 'handoff_description', None)
        output_type = getattr(agent, 'output_type', None)
        tool_use_behavior = getattr(agent, 'tool_use_behavior', 'run_llm_again')
        input_guardrails = getattr(agent, 'input_guardrails', None)
        output_guardrails = getattr(agent, 'output_guardrails', None)

        # 3. Call the existing service layer
        return await self.run_agent_streamed_auto_send(
            task_id=task_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            input_list=input_list,
            mcp_server_params=mcp_server_params or [],
            agent_name=agent_name,
            agent_instructions=agent_instructions,
            model=model,
            model_settings=model_settings,
            tools=tools,
            handoff_description=handoff_description,
            handoffs=handoffs,
            output_type=output_type,
            tool_use_behavior=tool_use_behavior,
            start_to_close_timeout=start_to_close_timeout,
            heartbeat_timeout=heartbeat_timeout,
            retry_policy=retry_policy,
            input_guardrails=input_guardrails,
            output_guardrails=output_guardrails,
            max_turns=max_turns,
            previous_response_id=previous_response_id,
        )
