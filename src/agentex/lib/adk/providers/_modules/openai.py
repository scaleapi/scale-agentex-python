from datetime import timedelta
from typing import Any, Literal

from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agents import Agent, RunResult, RunResultStreaming
from agents.agent import StopAtTools, ToolsToFinalOutputFunction
from agents.agent_output import AgentOutputSchemaBase
from agents.model_settings import ModelSettings
from agents.tool import Tool
from mcp import StdioServerParameters
from temporalio.common import RetryPolicy

from agentex import AsyncAgentex
from agentex.lib.core.adapters.streams.adapter_redis import RedisStreamRepository
from agentex.lib.core.services.adk.providers.openai import OpenAIService
from agentex.lib.core.services.adk.streaming import StreamingService
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.temporal.activities.adk.providers.openai_activities import (
    OpenAIActivityName,
    RunAgentAutoSendParams,
    RunAgentParams,
    RunAgentStreamedAutoSendParams,
)
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.lib.types.agent_results import (
    SerializableRunResult,
    SerializableRunResultStreaming,
)
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import in_temporal_workflow

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
            Literal["run_llm_again", "stop_on_first_tool"]
            | StopAtTools
            | ToolsToFinalOutputFunction
        ) = "run_llm_again",
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
                handoffs=handoffs,
                model=model,
                model_settings=model_settings,
                tools=tools,
                output_type=output_type,
                tool_use_behavior=tool_use_behavior,
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
            Literal["run_llm_again", "stop_on_first_tool"]
            | StopAtTools
            | ToolsToFinalOutputFunction
        ) = "run_llm_again",
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
                handoffs=handoffs,
                model=model,
                model_settings=model_settings,
                tools=tools,
                output_type=output_type,
                tool_use_behavior=tool_use_behavior,
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
            Literal["run_llm_again", "stop_on_first_tool"]
            | StopAtTools
            | ToolsToFinalOutputFunction
        ) = "run_llm_again",
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
            Literal["run_llm_again", "stop_on_first_tool"]
            | StopAtTools
            | ToolsToFinalOutputFunction
        ) = "run_llm_again",
        mcp_timeout_seconds: int | None = None,
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
            output_type: Optional output type.
            tool_use_behavior: Optional tool use behavior.
            mcp_timeout_seconds: Optional param to set the timeout threshold for the MCP servers. Defaults to 5 seconds.

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
            )
