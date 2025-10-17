# Standard library imports
from __future__ import annotations

import base64
from enum import Enum
from typing import Any, Literal, Optional
from contextlib import AsyncExitStack, asynccontextmanager
from collections.abc import Callable

import cloudpickle
from mcp import StdioServerParameters
from agents import RunResult, RunContextWrapper, RunResultStreaming
from pydantic import Field, PrivateAttr
from agents.mcp import MCPServerStdio, MCPServerStdioParams
from temporalio import activity
from agents.tool import (
    ComputerTool as OAIComputerTool,
    FunctionTool as OAIFunctionTool,
    WebSearchTool as OAIWebSearchTool,
    FileSearchTool as OAIFileSearchTool,
    LocalShellTool as OAILocalShellTool,
    CodeInterpreterTool as OAICodeInterpreterTool,
    ImageGenerationTool as OAIImageGenerationTool,
)
from agents.guardrail import InputGuardrail, OutputGuardrail
from agents.exceptions import InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered
from agents.model_settings import ModelSettings as OAIModelSettings
from openai.types.shared.reasoning import Reasoning
from openai.types.responses.response_includable import ResponseIncludable

from agentex.lib.utils import logging

# Third-party imports
from agentex.lib.types.tracing import BaseModelWithTraceParams

# Local imports
from agentex.lib.types.agent_results import (
    SerializableRunResult,
    SerializableRunResultStreaming,
)
from agentex.lib.core.services.adk.providers.openai import OpenAIService

logger = logging.make_logger(__name__)


class OpenAIActivityName(str, Enum):
    """Names of OpenAI agent activities."""

    RUN_AGENT = "run_agent"
    RUN_AGENT_AUTO_SEND = "run_agent_auto_send"
    # Note: RUN_AGENT_STREAMED is not supported in Temporal due to generator limitations
    RUN_AGENT_STREAMED_AUTO_SEND = "run_agent_streamed_auto_send"


class WebSearchTool(BaseModelWithTraceParams):
    """Temporal-compatible wrapper for WebSearchTool."""

    user_location: Optional[dict[str, Any]] = None  # UserLocation object
    search_context_size: Optional[Literal["low", "medium", "high"]] = "medium"

    def to_oai_function_tool(self) -> OAIWebSearchTool:
        kwargs = {}
        if self.user_location is not None:
            kwargs["user_location"] = self.user_location
        if self.search_context_size is not None:
            kwargs["search_context_size"] = self.search_context_size
        return OAIWebSearchTool(**kwargs)


class FileSearchTool(BaseModelWithTraceParams):
    """Temporal-compatible wrapper for FileSearchTool."""

    vector_store_ids: list[str]
    max_num_results: Optional[int] = None
    include_search_results: bool = False
    ranking_options: Optional[dict[str, Any]] = None
    filters: Optional[dict[str, Any]] = None

    def to_oai_function_tool(self):
        return OAIFileSearchTool(
            vector_store_ids=self.vector_store_ids,
            max_num_results=self.max_num_results,
            include_search_results=self.include_search_results,
            ranking_options=self.ranking_options,
            filters=self.filters,
        )


class ComputerTool(BaseModelWithTraceParams):
    """Temporal-compatible wrapper for ComputerTool."""

    # We need to serialize the computer object and safety check function
    computer_serialized: str = Field(default="", description="Serialized computer object")
    on_safety_check_serialized: str = Field(default="", description="Serialized safety check function")

    _computer: Any = PrivateAttr()
    _on_safety_check: Optional[Callable] = PrivateAttr()

    def __init__(
        self,
        *,
        computer: Any = None,
        on_safety_check: Optional[Callable] = None,
        **data,
    ):
        super().__init__(**data)
        if computer is not None:
            self.computer_serialized = self._serialize_callable(computer)
            self._computer = computer
        elif self.computer_serialized:
            self._computer = self._deserialize_callable(self.computer_serialized)

        if on_safety_check is not None:
            self.on_safety_check_serialized = self._serialize_callable(on_safety_check)
            self._on_safety_check = on_safety_check
        elif self.on_safety_check_serialized:
            self._on_safety_check = self._deserialize_callable(self.on_safety_check_serialized)

    @classmethod
    def _deserialize_callable(cls, serialized: str) -> Any:
        encoded = serialized.encode()
        serialized_bytes = base64.b64decode(encoded)
        return cloudpickle.loads(serialized_bytes)

    @classmethod
    def _serialize_callable(cls, func: Any) -> str:
        serialized_bytes = cloudpickle.dumps(func)
        encoded = base64.b64encode(serialized_bytes)
        return encoded.decode()

    def to_oai_function_tool(self):
        return OAIComputerTool(
            computer=self._computer,
            on_safety_check=self._on_safety_check,
        )


class CodeInterpreterTool(BaseModelWithTraceParams):
    """Temporal-compatible wrapper for CodeInterpreterTool."""

    tool_config: dict[str, Any] = Field(
        default_factory=lambda: {"type": "code_interpreter"}, description="Tool configuration dict"
    )

    def to_oai_function_tool(self):
        return OAICodeInterpreterTool(tool_config=self.tool_config)


class ImageGenerationTool(BaseModelWithTraceParams):
    """Temporal-compatible wrapper for ImageGenerationTool."""

    tool_config: dict[str, Any] = Field(
        default_factory=lambda: {"type": "image_generation"}, description="Tool configuration dict"
    )

    def to_oai_function_tool(self):
        return OAIImageGenerationTool(tool_config=self.tool_config)


class LocalShellTool(BaseModelWithTraceParams):
    """Temporal-compatible wrapper for LocalShellTool."""

    executor_serialized: str = Field(default="", description="Serialized LocalShellExecutor object")

    _executor: Any = PrivateAttr()

    def __init__(
        self,
        *,
        executor: Any = None,
        **data,
    ):
        super().__init__(**data)
        if executor is not None:
            self.executor_serialized = self._serialize_callable(executor)
            self._executor = executor
        elif self.executor_serialized:
            self._executor = self._deserialize_callable(self.executor_serialized)

    @classmethod
    def _deserialize_callable(cls, serialized: str) -> Any:
        encoded = serialized.encode()
        serialized_bytes = base64.b64decode(encoded)
        return cloudpickle.loads(serialized_bytes)

    @classmethod
    def _serialize_callable(cls, func: Any) -> str:
        serialized_bytes = cloudpickle.dumps(func)
        encoded = base64.b64encode(serialized_bytes)
        return encoded.decode()

    def to_oai_function_tool(self):
        return OAILocalShellTool(executor=self._executor)


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
                raise ValueError("One of `on_invoke_tool` or `on_invoke_tool_serialized` should be set")
            else:
                on_invoke_tool = self._deserialize_callable(self.on_invoke_tool_serialized)
        else:
            self.on_invoke_tool_serialized = self._serialize_callable(on_invoke_tool)

        self._on_invoke_tool = on_invoke_tool

    @classmethod
    def _deserialize_callable(cls, serialized: str) -> Callable[[RunContextWrapper, str], Any]:
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
            self._on_invoke_tool = self._deserialize_callable(self.on_invoke_tool_serialized)
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


class TemporalInputGuardrail(BaseModelWithTraceParams):
    """Temporal-compatible wrapper for InputGuardrail with function
    serialization."""

    name: str
    _guardrail_function: Callable = PrivateAttr()
    guardrail_function_serialized: str = Field(
        default="",
        description=(
            "Serialized guardrail function. Set automatically during initialization. "
            "Pass `guardrail_function` to the constructor instead."
        ),
    )

    def __init__(
        self,
        *,
        guardrail_function: Optional[Callable] = None,
        **data,
    ):
        """Initialize with function serialization support for Temporal."""
        super().__init__(**data)
        if not guardrail_function:
            if not self.guardrail_function_serialized:
                raise ValueError("One of `guardrail_function` or `guardrail_function_serialized` should be set")
            else:
                guardrail_function = self._deserialize_callable(self.guardrail_function_serialized)
        else:
            self.guardrail_function_serialized = self._serialize_callable(guardrail_function)

        self._guardrail_function = guardrail_function

    @classmethod
    def _deserialize_callable(cls, serialized: str) -> Callable:
        encoded = serialized.encode()
        serialized_bytes = base64.b64decode(encoded)
        return cloudpickle.loads(serialized_bytes)

    @classmethod
    def _serialize_callable(cls, func: Callable) -> str:
        serialized_bytes = cloudpickle.dumps(func)
        encoded = base64.b64encode(serialized_bytes)
        return encoded.decode()

    @property
    def guardrail_function(self) -> Callable:
        if self._guardrail_function is None and self.guardrail_function_serialized:
            self._guardrail_function = self._deserialize_callable(self.guardrail_function_serialized)
        return self._guardrail_function

    @guardrail_function.setter
    def guardrail_function(self, value: Callable):
        self.guardrail_function_serialized = self._serialize_callable(value)
        self._guardrail_function = value

    def to_oai_input_guardrail(self) -> InputGuardrail:
        """Convert to OpenAI InputGuardrail."""
        return InputGuardrail(guardrail_function=self.guardrail_function, name=self.name)


class TemporalOutputGuardrail(BaseModelWithTraceParams):
    """Temporal-compatible wrapper for OutputGuardrail with function
    serialization."""

    name: str
    _guardrail_function: Callable = PrivateAttr()
    guardrail_function_serialized: str = Field(
        default="",
        description=(
            "Serialized guardrail function. Set automatically during initialization. "
            "Pass `guardrail_function` to the constructor instead."
        ),
    )

    def __init__(
        self,
        *,
        guardrail_function: Optional[Callable] = None,
        **data,
    ):
        """Initialize with function serialization support for Temporal."""
        super().__init__(**data)
        if not guardrail_function:
            if not self.guardrail_function_serialized:
                raise ValueError("One of `guardrail_function` or `guardrail_function_serialized` should be set")
            else:
                guardrail_function = self._deserialize_callable(self.guardrail_function_serialized)
        else:
            self.guardrail_function_serialized = self._serialize_callable(guardrail_function)

        self._guardrail_function = guardrail_function

    @classmethod
    def _deserialize_callable(cls, serialized: str) -> Callable:
        encoded = serialized.encode()
        serialized_bytes = base64.b64decode(encoded)
        return cloudpickle.loads(serialized_bytes)

    @classmethod
    def _serialize_callable(cls, func: Callable) -> str:
        serialized_bytes = cloudpickle.dumps(func)
        encoded = base64.b64encode(serialized_bytes)
        return encoded.decode()

    @property
    def guardrail_function(self) -> Callable:
        if self._guardrail_function is None and self.guardrail_function_serialized:
            self._guardrail_function = self._deserialize_callable(self.guardrail_function_serialized)
        return self._guardrail_function

    @guardrail_function.setter
    def guardrail_function(self, value: Callable):
        self.guardrail_function_serialized = self._serialize_callable(value)
        self._guardrail_function = value

    def to_oai_output_guardrail(self) -> OutputGuardrail:
        """Convert to OpenAI OutputGuardrail."""
        return OutputGuardrail(guardrail_function=self.guardrail_function, name=self.name)


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
        return OAIModelSettings(**self.model_dump(exclude=["trace_id", "parent_span_id"]))


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
    tools: (
        list[
            FunctionTool
            | WebSearchTool
            | FileSearchTool
            | ComputerTool
            | CodeInterpreterTool
            | ImageGenerationTool
            | LocalShellTool
        ]
        | None
    ) = None
    output_type: Any = None
    tool_use_behavior: Literal["run_llm_again", "stop_on_first_tool"] = "run_llm_again"
    mcp_timeout_seconds: int | None = None
    input_guardrails: list[TemporalInputGuardrail] | None = None
    output_guardrails: list[TemporalOutputGuardrail] | None = None
    max_turns: int | None = None
    previous_response_id: str | None = None


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
        # Convert Temporal guardrails to OpenAI guardrails
        input_guardrails = None
        if params.input_guardrails:
            input_guardrails = [g.to_oai_input_guardrail() for g in params.input_guardrails]

        output_guardrails = None
        if params.output_guardrails:
            output_guardrails = [g.to_oai_output_guardrail() for g in params.output_guardrails]

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
            input_guardrails=input_guardrails,
            output_guardrails=output_guardrails,
            mcp_timeout_seconds=params.mcp_timeout_seconds,
            max_turns=params.max_turns,
            previous_response_id=params.previous_response_id,
        )
        return self._to_serializable_run_result(result)

    @activity.defn(name=OpenAIActivityName.RUN_AGENT_AUTO_SEND)
    async def run_agent_auto_send(self, params: RunAgentAutoSendParams) -> SerializableRunResult:
        """Run an agent with automatic TaskMessage creation."""
        # Convert Temporal guardrails to OpenAI guardrails
        input_guardrails = None
        if params.input_guardrails:
            input_guardrails = [g.to_oai_input_guardrail() for g in params.input_guardrails]

        output_guardrails = None
        if params.output_guardrails:
            output_guardrails = [g.to_oai_output_guardrail() for g in params.output_guardrails]

        try:
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
                input_guardrails=input_guardrails,
                output_guardrails=output_guardrails,
                mcp_timeout_seconds=params.mcp_timeout_seconds,
                max_turns=params.max_turns,
                previous_response_id=params.previous_response_id,
            )
            return self._to_serializable_run_result(result)
        except InputGuardrailTripwireTriggered as e:
            # Handle guardrail trigger gracefully
            rejection_message = (
                "I'm sorry, but I cannot process this request due to a guardrail. Please try a different question."
            )

            # Try to extract rejection message from the guardrail result
            if hasattr(e, "guardrail_result") and hasattr(e.guardrail_result, "output"):
                output_info = getattr(e.guardrail_result.output, "output_info", {})
                if isinstance(output_info, dict) and "rejection_message" in output_info:
                    rejection_message = output_info["rejection_message"]

            # Build the final input list with the rejection message
            final_input_list = list(params.input_list or [])
            final_input_list.append({"role": "assistant", "content": rejection_message})

            return SerializableRunResult(final_output=rejection_message, final_input_list=final_input_list)
        except OutputGuardrailTripwireTriggered as e:
            # Handle output guardrail trigger gracefully
            rejection_message = (
                "I'm sorry, but I cannot provide this response due to a guardrail. Please try a different question."
            )

            # Try to extract rejection message from the guardrail result
            if hasattr(e, "guardrail_result") and hasattr(e.guardrail_result, "output"):
                output_info = getattr(e.guardrail_result.output, "output_info", {})
                if isinstance(output_info, dict) and "rejection_message" in output_info:
                    rejection_message = output_info["rejection_message"]

            # Build the final input list with the rejection message
            final_input_list = list(params.input_list or [])
            final_input_list.append({"role": "assistant", "content": rejection_message})

            return SerializableRunResult(final_output=rejection_message, final_input_list=final_input_list)

    @activity.defn(name=OpenAIActivityName.RUN_AGENT_STREAMED_AUTO_SEND)
    async def run_agent_streamed_auto_send(
        self, params: RunAgentStreamedAutoSendParams
    ) -> SerializableRunResultStreaming:
        """Run an agent with streaming and automatic TaskMessage creation."""

        # Convert Temporal guardrails to OpenAI guardrails
        input_guardrails = None
        if params.input_guardrails:
            input_guardrails = [g.to_oai_input_guardrail() for g in params.input_guardrails]

        output_guardrails = None
        if params.output_guardrails:
            output_guardrails = [g.to_oai_output_guardrail() for g in params.output_guardrails]

        try:
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
                input_guardrails=input_guardrails,
                output_guardrails=output_guardrails,
                mcp_timeout_seconds=params.mcp_timeout_seconds,
                max_turns=params.max_turns,
                previous_response_id=params.previous_response_id,
            )
            return self._to_serializable_run_result_streaming(result)
        except InputGuardrailTripwireTriggered as e:
            # Handle guardrail trigger gracefully
            rejection_message = (
                "I'm sorry, but I cannot process this request due to a guardrail. Please try a different question."
            )

            # Try to extract rejection message from the guardrail result
            if hasattr(e, "guardrail_result") and hasattr(e.guardrail_result, "output"):
                output_info = getattr(e.guardrail_result.output, "output_info", {})
                if isinstance(output_info, dict) and "rejection_message" in output_info:
                    rejection_message = output_info["rejection_message"]

            # Build the final input list with the rejection message
            final_input_list = list(params.input_list or [])
            final_input_list.append({"role": "assistant", "content": rejection_message})

            return SerializableRunResultStreaming(final_output=rejection_message, final_input_list=final_input_list)
        except OutputGuardrailTripwireTriggered as e:
            # Handle output guardrail trigger gracefully
            rejection_message = (
                "I'm sorry, but I cannot provide this response due to a guardrail. Please try a different question."
            )

            # Try to extract rejection message from the guardrail result
            if hasattr(e, "guardrail_result") and hasattr(e.guardrail_result, "output"):
                output_info = getattr(e.guardrail_result.output, "output_info", {})
                if isinstance(output_info, dict) and "rejection_message" in output_info:
                    rejection_message = output_info["rejection_message"]

            # Build the final input list with the rejection message
            final_input_list = list(params.input_list or [])
            final_input_list.append({"role": "assistant", "content": rejection_message})

            return SerializableRunResultStreaming(final_output=rejection_message, final_input_list=final_input_list)

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
