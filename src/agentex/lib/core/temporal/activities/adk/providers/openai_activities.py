# Standard library imports
import base64
from collections.abc import Callable
from contextlib import AsyncExitStack, asynccontextmanager
from enum import Enum
from typing import Any, Literal, Optional, override

from pydantic import Field, PrivateAttr

import cloudpickle
from agents import RunContextWrapper, RunResult, RunResultStreaming
from agents.mcp import MCPServerStdio, MCPServerStdioParams
from agents.model_settings import ModelSettings as OAIModelSettings
from agents.tool import FunctionTool as OAIFunctionTool
from mcp import StdioServerParameters
from openai.types.responses.response_includable import ResponseIncludable
from openai.types.shared.reasoning import Reasoning
from temporalio import activity

from agentex.lib.core.services.adk.providers.openai import OpenAIService

# Local imports
from agentex.lib.types.agent_results import (
    SerializableRunResult,
    SerializableRunResultStreaming,
)

# Third-party imports
from agentex.lib.types.tracing import BaseModelWithTraceParams
from agentex.lib.utils import logging

logger = logging.make_logger(__name__)


class OpenAIActivityName(str, Enum):
    """Names of OpenAI agent activities."""

    RUN_AGENT = "run_agent"
    RUN_AGENT_AUTO_SEND = "run_agent_auto_send"
    # Note: RUN_AGENT_STREAMED is not supported in Temporal due to generator limitations
    RUN_AGENT_STREAMED_AUTO_SEND = "run_agent_streamed_auto_send"


class FunctionTool(BaseModelWithTraceParams):
    name: str
    description: str
    params_json_schema: dict[str, Any]

    strict_json_schema: bool = True
    is_enabled: bool = True

    _on_invoke_tool: Callable[[RunContextWrapper, str], Any] = PrivateAttr()
    on_invoke_tool_serialized: str = Field(
        default="",
        description=(
            "Normally will be set automatically during initialization and"
            " doesn't need to be passed. "
            "Instead, pass `on_invoke_tool` to the constructor. "
            "See the __init__ method for details."
        ),
    )

    def __init__(
        self,
        *,
        on_invoke_tool: Optional[Callable[[RunContextWrapper, str], Any]] = None,
        **data,
    ):
        """
        Initialize a FunctionTool with hacks to support serialization of the
         on_invoke_tool callable arg. This is required to facilitate over-the-wire
         communication of this object to/from temporal services/workers.

        Args:
            on_invoke_tool: The callable to invoke when the tool is called.
            **data: Additional data to initialize the FunctionTool.
        """
        super().__init__(**data)
        if not on_invoke_tool:
            if not self.on_invoke_tool_serialized:
                raise ValueError(
                    "One of `on_invoke_tool` or `on_invoke_tool_serialized` should be set"
                )
            else:
                on_invoke_tool = self._deserialize_callable(
                    self.on_invoke_tool_serialized
                )
        else:
            self.on_invoke_tool_serialized = self._serialize_callable(on_invoke_tool)

        self._on_invoke_tool = on_invoke_tool

    @classmethod
    def _deserialize_callable(
        cls, serialized: str
    ) -> Callable[[RunContextWrapper, str], Any]:
        encoded = serialized.encode()
        serialized_bytes = base64.b64decode(encoded)
        return cloudpickle.loads(serialized_bytes)

    @classmethod
    def _serialize_callable(cls, func: Callable) -> str:
        serialized_bytes = cloudpickle.dumps(func)
        encoded = base64.b64encode(serialized_bytes)
        return encoded.decode()

    @property
    def on_invoke_tool(self) -> Callable[[RunContextWrapper, str], Any]:
        if self._on_invoke_tool is None and self.on_invoke_tool_serialized:
            self._on_invoke_tool = self._deserialize_callable(
                self.on_invoke_tool_serialized
            )
        return self._on_invoke_tool
    
    @on_invoke_tool.setter
    def on_invoke_tool(self, value: Callable[[RunContextWrapper, str], Any]):
        self.on_invoke_tool_serialized = self._serialize_callable(value)
        self._on_invoke_tool = value

    def to_oai_function_tool(self) -> OAIFunctionTool:
        """Convert to OpenAI function tool, excluding serialization fields."""
        # Create a dictionary with only the fields OAIFunctionTool expects
        data = self.model_dump(
            exclude={
                "trace_id",
                "parent_span_id",
                "_on_invoke_tool",
                "on_invoke_tool_serialized",
            }
        )
        # Add the callable for OAI tool since properties are not serialized
        data["on_invoke_tool"] = self.on_invoke_tool
        return OAIFunctionTool(**data)


class ModelSettings(BaseModelWithTraceParams):
    temperature: float | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    tool_choice: Literal["auto", "required", "none"] | str | None = None
    parallel_tool_calls: bool | None = None
    truncation: Literal["auto", "disabled"] | None = None
    max_tokens: int | None = None
    reasoning: Reasoning | None = None
    metadata: dict[str, str] | None = None
    store: bool | None = None
    include_usage: bool | None = None
    response_include: list[ResponseIncludable] | None = None
    extra_body: dict[str, str] | None = None
    extra_headers: dict[str, str] | None = None
    extra_args: dict[str, Any] | None = None

    def to_oai_model_settings(self) -> OAIModelSettings:
        return OAIModelSettings(
            **self.model_dump(exclude=["trace_id", "parent_span_id"])
        )


class RunAgentParams(BaseModelWithTraceParams):
    """Parameters for running an agent without streaming."""

    input_list: list[dict]
    mcp_server_params: list[StdioServerParameters]
    agent_name: str
    agent_instructions: str
    handoff_description: str | None = None
    handoffs: list["RunAgentParams"] | None = None
    model: str | None = None
    model_settings: ModelSettings | None = None
    tools: list[FunctionTool] | None = None
    output_type: Any = None
    tool_use_behavior: Literal["run_llm_again", "stop_on_first_tool"] = "run_llm_again"
    mcp_timeout_seconds: int | None = None


class RunAgentAutoSendParams(RunAgentParams):
    """Parameters for running an agent with automatic TaskMessage creation."""

    task_id: str


class RunAgentStreamedAutoSendParams(RunAgentParams):
    """Parameters for running an agent with streaming and automatic TaskMessage creation."""

    task_id: str


@asynccontextmanager
async def mcp_server_context(mcp_server_params: list[StdioServerParameters]):
    """Context manager for MCP servers."""
    servers: list[MCPServerStdio] = []
    for params in mcp_server_params:
        server = MCPServerStdio(
            name=f"Server: {params.command}",
            params=MCPServerStdioParams(**params.model_dump()),
            cache_tools_list=True,
            client_session_timeout_seconds=60,
        )
        servers.append(server)

    async with AsyncExitStack() as stack:
        for server in servers:
            await stack.enter_async_context(server)
        yield servers


class OpenAIActivities:
    """Activities for OpenAI agent operations."""

    def __init__(self, openai_service: OpenAIService):
        self._openai_service = openai_service

    @activity.defn(name=OpenAIActivityName.RUN_AGENT)
    async def run_agent(self, params: RunAgentParams) -> SerializableRunResult:
        """Run an agent without streaming or TaskMessage creation."""
        result = await self._openai_service.run_agent(
            input_list=params.input_list,
            mcp_server_params=params.mcp_server_params,
            agent_name=params.agent_name,
            agent_instructions=params.agent_instructions,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
            handoff_description=params.handoff_description,
            handoffs=params.handoffs,
            model=params.model,
            model_settings=params.model_settings,
            tools=params.tools,
            output_type=params.output_type,
            tool_use_behavior=params.tool_use_behavior,
        )
        return self._to_serializable_run_result(result)

    @activity.defn(name=OpenAIActivityName.RUN_AGENT_AUTO_SEND)
    async def run_agent_auto_send(
        self, params: RunAgentAutoSendParams
    ) -> SerializableRunResult:
        """Run an agent with automatic TaskMessage creation."""
        result = await self._openai_service.run_agent_auto_send(
            task_id=params.task_id,
            input_list=params.input_list,
            mcp_server_params=params.mcp_server_params,
            agent_name=params.agent_name,
            agent_instructions=params.agent_instructions,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
            handoff_description=params.handoff_description,
            handoffs=params.handoffs,
            model=params.model,
            model_settings=params.model_settings,
            tools=params.tools,
            output_type=params.output_type,
            tool_use_behavior=params.tool_use_behavior,
        )
        return self._to_serializable_run_result(result)

    @activity.defn(name=OpenAIActivityName.RUN_AGENT_STREAMED_AUTO_SEND)
    async def run_agent_streamed_auto_send(
        self, params: RunAgentStreamedAutoSendParams
    ) -> SerializableRunResultStreaming:
        """Run an agent with streaming and automatic TaskMessage creation."""
        result = await self._openai_service.run_agent_streamed_auto_send(
            task_id=params.task_id,
            input_list=params.input_list,
            mcp_server_params=params.mcp_server_params,
            agent_name=params.agent_name,
            agent_instructions=params.agent_instructions,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
            handoff_description=params.handoff_description,
            handoffs=params.handoffs,
            model=params.model,
            model_settings=params.model_settings,
            tools=params.tools,
            output_type=params.output_type,
            tool_use_behavior=params.tool_use_behavior,
        )
        return self._to_serializable_run_result_streaming(result)

    @staticmethod
    def _to_serializable_run_result(result: RunResult) -> SerializableRunResult:
        """Convert RunResult to SerializableRunResult."""
        return SerializableRunResult(
            final_output=result.final_output,
            final_input_list=result.to_input_list(),
        )

    @staticmethod
    def _to_serializable_run_result_streaming(
        result: RunResultStreaming,
    ) -> SerializableRunResultStreaming:
        """Convert RunResultStreaming to SerializableRunResultStreaming."""
        return SerializableRunResultStreaming(
            final_output=result.final_output,
            final_input_list=result.to_input_list(),
        )
