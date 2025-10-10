"""Custom Temporal Model Provider with streaming support for OpenAI agents."""
from __future__ import annotations

import uuid
import logging
from typing import Any, List, Union, Optional, override

from agents import (
    Tool,
    Model,
    Handoff,
    FunctionTool,
    ModelTracing,
    ModelProvider,
    ModelResponse,
    ModelSettings,
    TResponseInputItem,
    AgentOutputSchemaBase,
)
from openai import NOT_GIVEN, AsyncOpenAI
from agents.tool import (
    ComputerTool,
    HostedMCPTool,
    WebSearchTool,
    FileSearchTool,
    LocalShellTool,
    CodeInterpreterTool,
    ImageGenerationTool,
)
from agents.usage import Usage, InputTokensDetails, OutputTokensDetails  # type: ignore[attr-defined]
from agents.model_settings import MCPToolChoice
from openai.types.responses import (
    ResponseOutputText,
    ResponseOutputMessage,
    ResponseCompletedEvent,
    ResponseTextDeltaEvent,
    ResponseFunctionToolCall,
    ResponseOutputItemDoneEvent,
    # Event types for proper type checking
    ResponseOutputItemAddedEvent,
    ResponseReasoningTextDeltaEvent,
    ResponseReasoningSummaryPartDoneEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseReasoningSummaryPartAddedEvent,
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
)

# AgentEx SDK imports
from agentex.lib import adk
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.task_message_delta import TextDelta, ReasoningContentDelta, ReasoningSummaryDelta
from agentex.types.task_message_update import StreamTaskMessageFull, StreamTaskMessageDelta
from agentex.types.task_message_content import TextContent, ReasoningContent
from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import (
    streaming_task_id,
    streaming_trace_id,
    streaming_parent_span_id,
)

# Create logger for this module
logger = logging.getLogger("agentex.temporal.streaming")

class TemporalStreamingModel(Model):
    """Custom model implementation with streaming support."""

    def __init__(self, model_name: str = "gpt-4o", _use_responses_api: bool = True):
        """Initialize the streaming model with OpenAI client and model name."""
        # Match the default behavior with no retries (Temporal handles retries)
        self.client = AsyncOpenAI(max_retries=0)
        self.model_name = model_name
        # Always use Responses API for all models
        self.use_responses_api = True

        # Initialize tracer as a class variable
        agentex_client = create_async_agentex_client()
        self.tracer = AsyncTracer(agentex_client)

        logger.info(f"[TemporalStreamingModel] Initialized model={self.model_name}, use_responses_api={self.use_responses_api}, tracer=initialized")

    def _non_null_or_not_given(self, value: Any) -> Any:
        """Convert None to NOT_GIVEN sentinel, matching OpenAI SDK pattern."""
        return value if value is not None else NOT_GIVEN

    def _prepare_response_input(self, input: Union[str, list[TResponseInputItem]]) -> List[dict]:
        """Convert input to Responses API format.

        Args:
            input: Either a string prompt or list of ResponseInputItem messages

        Returns:
            List of input items in Responses API format
        """
        response_input = []

        if isinstance(input, list):
            # Process list of ResponseInputItem objects
            for _idx, item in enumerate(input):
                # Convert to dict if needed
                if isinstance(item, dict):
                    item_dict = item
                else:
                    item_dict = item.model_dump() if hasattr(item, 'model_dump') else item

                item_type = item_dict.get("type")

                if item_type == "message":
                    # ResponseOutputMessage format
                    role = item_dict.get("role", "assistant")
                    content_list = item_dict.get("content", [])

                    # Build content array
                    content_array = []
                    for content_item in content_list:
                        if isinstance(content_item, dict):
                            if content_item.get("type") == "output_text":
                                # For assistant messages, keep as output_text
                                # For user messages, convert to input_text
                                if role == "user":
                                    content_array.append({
                                        "type": "input_text",
                                        "text": content_item.get("text", "")
                                    })
                                else:
                                    content_array.append({
                                        "type": "output_text",
                                        "text": content_item.get("text", "")
                                    })
                            else:
                                content_array.append(content_item)

                    response_input.append({
                        "type": "message",
                        "role": role,
                        "content": content_array
                    })

                elif item_type == "function_call":
                    # Function call from previous response
                    logger.debug(f"[Responses API] function_call item keys: {list(item_dict.keys())}")
                    call_id = item_dict.get("call_id") or item_dict.get("id")
                    if not call_id:
                        logger.debug(f"[Responses API] WARNING: No call_id found in function_call item!")
                        logger.debug(f"[Responses API] Full item: {item_dict}")
                        # Generate a fallback ID if missing
                        call_id = f"call_{uuid.uuid4().hex[:8]}"
                        logger.debug(f"[Responses API] Generated fallback call_id: {call_id}")
                    logger.debug(f"[Responses API] Adding function_call with call_id={call_id}, name={item_dict.get('name')}")
                    response_input.append({
                        "type": "function_call",
                        "call_id": call_id,  # API expects 'call_id' not 'id'
                        "name": item_dict.get("name", ""),
                        "arguments": item_dict.get("arguments", "{}"),
                    })

                elif item_type == "function_call_output":
                    # Function output/response
                    call_id = item_dict.get("call_id")
                    if not call_id:
                        logger.debug(f"[Responses API] WARNING: No call_id in function_call_output!")
                        # Try to find it from id field
                        call_id = item_dict.get("id")
                    response_input.append({
                        "type": "function_call_output",
                        "call_id": call_id or "",
                        "output": item_dict.get("output", "")
                    })

                elif item_dict.get("role") == "user":
                    # Simple user message
                    response_input.append({
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": item_dict.get("content", "")}]
                    })

                elif item_dict.get("role") == "tool":
                    # Tool message
                    response_input.append({
                        "type": "function_call_output",
                        "call_id": item_dict.get("tool_call_id"),
                        "output": item_dict.get("content")
                    })
                else:
                    logger.debug(f"[Responses API] Skipping unhandled item type: {item_type}, role: {item_dict.get('role')}")

        elif isinstance(input, str):
            # Simple string input
            response_input.append({
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": input}]
            })

        return response_input

    def _convert_tools(self, tools: list[Tool], handoffs: list[Handoff]) -> tuple[List[dict], List[str]]:
        """Convert tools and handoffs to Responses API format.

        Args:
            tools: List of Tool objects
            handoffs: List of Handoff objects

        Returns:
            Tuple of (converted_tools, include_list) where include_list contains
            additional response data to request
        """
        response_tools = []
        tool_includes = []

        # Check for multiple computer tools (only one allowed)
        computer_tools = [tool for tool in tools if isinstance(tool, ComputerTool)]
        if len(computer_tools) > 1:
            raise ValueError(f"You can only provide one computer tool. Got {len(computer_tools)}")

        # Convert each tool based on its type
        for tool in tools:
            if isinstance(tool, FunctionTool):
                response_tools.append({
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.params_json_schema if tool.params_json_schema else {},
                    "strict": tool.strict_json_schema,
                })

            elif isinstance(tool, WebSearchTool):
                tool_config = {
                    "type": "web_search",
                }
                # filters attribute was removed from WebSearchTool API
                if hasattr(tool, 'user_location') and tool.user_location is not None:
                    tool_config["user_location"] = tool.user_location
                if hasattr(tool, 'search_context_size') and tool.search_context_size is not None:
                    tool_config["search_context_size"] = tool.search_context_size
                response_tools.append(tool_config)

            elif isinstance(tool, FileSearchTool):
                tool_config = {
                    "type": "file_search",
                    "vector_store_ids": tool.vector_store_ids,
                }
                if tool.max_num_results:
                    tool_config["max_num_results"] = tool.max_num_results
                if tool.ranking_options:
                    tool_config["ranking_options"] = tool.ranking_options
                if tool.filters:
                    tool_config["filters"] = tool.filters
                response_tools.append(tool_config)

                # Add include for file search results if needed
                if tool.include_search_results:
                    tool_includes.append("file_search_call.results")

            elif isinstance(tool, ComputerTool):
                response_tools.append({
                    "type": "computer_use_preview",
                    "environment": tool.computer.environment,
                    "display_width": tool.computer.dimensions[0],
                    "display_height": tool.computer.dimensions[1],
                })

            elif isinstance(tool, HostedMCPTool):
                response_tools.append(tool.tool_config)

            elif isinstance(tool, ImageGenerationTool):
                response_tools.append(tool.tool_config)

            elif isinstance(tool, CodeInterpreterTool):
                response_tools.append(tool.tool_config)

            elif isinstance(tool, LocalShellTool):
                # LocalShellTool API changed - no longer has working_directory
                # The executor handles execution details internally
                response_tools.append({
                    "type": "local_shell",
                })

            else:
                logger.warning(f"Unknown tool type: {type(tool).__name__}, skipping")

        # Convert handoffs (always function tools)
        for handoff in handoffs:
            response_tools.append({
                "type": "function",
                "name": handoff.tool_name,
                "description": handoff.tool_description or f"Transfer to {handoff.agent_name}",
                "parameters": handoff.input_json_schema if handoff.input_json_schema else {},
            })

        return response_tools, tool_includes

    def _build_reasoning_param(self, model_settings: ModelSettings) -> Any:
        """Build reasoning parameter from model settings.

        Args:
            model_settings: Model configuration settings

        Returns:
            Reasoning parameter dict or NOT_GIVEN
        """
        if not model_settings.reasoning:
            return NOT_GIVEN

        if hasattr(model_settings.reasoning, 'effort') and model_settings.reasoning.effort:
            # For Responses API, reasoning is an object
            reasoning_param = {
                "effort": model_settings.reasoning.effort,
            }
            # Add generate_summary if specified and not None
            if hasattr(model_settings.reasoning, 'generate_summary') and model_settings.reasoning.generate_summary is not None:
                reasoning_param["summary"] = model_settings.reasoning.generate_summary
            logger.debug(f"[TemporalStreamingModel] Using reasoning param: {reasoning_param}")
            return reasoning_param

        return NOT_GIVEN

    def _convert_tool_choice(self, tool_choice: Any) -> Any:
        """Convert tool_choice to Responses API format.

        Args:
            tool_choice: Tool choice from model settings

        Returns:
            Converted tool choice or NOT_GIVEN
        """
        if tool_choice is None:
            return NOT_GIVEN

        if isinstance(tool_choice, MCPToolChoice):
            # MCP tool choice with server label
            return {
                "server_label": tool_choice.server_label,
                "type": "mcp",
                "name": tool_choice.name,
            }
        elif tool_choice == "required":
            return "required"
        elif tool_choice == "auto":
            return "auto"
        elif tool_choice == "none":
            return "none"
        elif tool_choice == "file_search":
            return {"type": "file_search"}
        elif tool_choice == "web_search":
            return {"type": "web_search"}
        elif tool_choice == "web_search_preview":
            return {"type": "web_search_preview"}
        elif tool_choice == "computer_use_preview":
            return {"type": "computer_use_preview"}
        elif tool_choice == "image_generation":
            return {"type": "image_generation"}
        elif tool_choice == "code_interpreter":
            return {"type": "code_interpreter"}
        elif tool_choice == "mcp":
            # Generic MCP without specific tool
            return {"type": "mcp"}
        elif isinstance(tool_choice, str):
            # Specific function tool by name
            return {
                "type": "function",
                "name": tool_choice,
            }
        else:
            # Pass through as-is for other types
            return tool_choice

    @override
    async def get_response(
        self,
        system_instructions: Optional[str],
        input: Union[str, list[TResponseInputItem]],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: Optional[AgentOutputSchemaBase],
        handoffs: list[Handoff],
        tracing: ModelTracing,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ) -> ModelResponse:
        """Get a non-streaming response from the model with streaming to Redis.

        This method is used by Temporal activities and needs to return a complete
        response, but we stream the response to Redis while generating it.
        """
        
        task_id = streaming_task_id.get()
        trace_id = streaming_trace_id.get()
        parent_span_id = streaming_parent_span_id.get()

        if not task_id or not trace_id or not parent_span_id:
            raise ValueError("task_id, trace_id, and parent_span_id are required for streaming with Responses API")

        trace = self.tracer.trace(trace_id)

        async with trace.span(
            parent_id=parent_span_id,
            name="streaming_model_get_response",
            input={
                "model": self.model_name,
                "has_system_instructions": system_instructions is not None,
                "input_type": type(input).__name__,
                "tools_count": len(tools) if tools else 0,
                "handoffs_count": len(handoffs) if handoffs else 0,
            },
        ) as span:
            # Always use Responses API for streaming
            if not task_id:
                # If no task_id, we can't use streaming - this shouldn't happen normally
                raise ValueError("task_id is required for streaming with Responses API")

            logger.info(f"[TemporalStreamingModel] Using Responses API for {self.model_name}")

            try:
                # Prepare input using helper method
                response_input = self._prepare_response_input(input)

                # Convert tools and handoffs using helper method
                response_tools, tool_includes = self._convert_tools(tools, handoffs)
                openai_tools = response_tools if response_tools else None

                # Build reasoning parameter using helper method
                reasoning_param = self._build_reasoning_param(model_settings)

                # Convert tool_choice using helper method
                tool_choice = self._convert_tool_choice(model_settings.tool_choice)

                # Build include list for response data
                include_list = []
                # Add tool-specific includes
                if tool_includes:
                    include_list.extend(tool_includes)
                # Add user-specified includes
                if model_settings.response_include:
                    include_list.extend(model_settings.response_include)
                # Add logprobs include if top_logprobs is set
                if model_settings.top_logprobs is not None:
                    include_list.append("message.output_text.logprobs")
                # Build response format for verbosity and structured output
                response_format = NOT_GIVEN
                if output_schema is not None:
                    # Handle structured output schema
                    # This would need conversion logic similar to Converter.get_response_format
                    pass  # TODO: Implement output_schema conversion
                elif model_settings.verbosity is not None:
                    response_format = {"verbosity": model_settings.verbosity}

                # Build extra_args dict for additional parameters
                extra_args = dict(model_settings.extra_args or {})
                if model_settings.top_logprobs is not None:
                    extra_args["top_logprobs"] = model_settings.top_logprobs

                # Create the response stream using Responses API
                logger.debug(f"[TemporalStreamingModel] Creating response stream with Responses API")
                stream = await self.client.responses.create(  # type: ignore[call-overload]

                    model=self.model_name,
                    input=response_input,
                    instructions=system_instructions,
                    tools=openai_tools or NOT_GIVEN,
                    stream=True,
                    # Temperature and sampling parameters
                    temperature=self._non_null_or_not_given(model_settings.temperature),
                    max_output_tokens=self._non_null_or_not_given(model_settings.max_tokens),
                    top_p=self._non_null_or_not_given(model_settings.top_p),
                    # Note: frequency_penalty and presence_penalty are not supported by Responses API
                    # Tool and reasoning parameters
                    reasoning=reasoning_param,
                    tool_choice=tool_choice,
                    parallel_tool_calls=self._non_null_or_not_given(model_settings.parallel_tool_calls),
                    # Context and truncation
                    truncation=self._non_null_or_not_given(model_settings.truncation),
                    # Response configuration
                    text=response_format,
                    include=include_list if include_list else NOT_GIVEN,
                    # Metadata and storage
                    metadata=self._non_null_or_not_given(model_settings.metadata),
                    store=self._non_null_or_not_given(model_settings.store),
                    # Extra customization
                    extra_headers=model_settings.extra_headers,
                    extra_query=model_settings.extra_query,
                    extra_body=model_settings.extra_body,
                    # Any additional parameters from extra_args
                    **extra_args,
                )

                # Process the stream of events from Responses API
                output_items = []
                current_text = ""
                reasoning_context = None
                reasoning_summaries = []
                reasoning_contents = []
                current_reasoning_summary = ""
                event_count = 0

                # We expect task_id to always be provided for streaming
                if not task_id:
                    raise ValueError("[TemporalStreamingModel] task_id is required for streaming model")

                # Use proper async with context manager for streaming to Redis
                async with adk.streaming.streaming_task_message_context(
                    task_id=task_id,
                    initial_content=TextContent(
                        author="agent",
                        content="",
                        format="markdown",
                    ),
                ) as streaming_context:
                    # Process events from the Responses API stream
                    function_calls_in_progress = {}  # Track function calls being streamed

                    async for event in stream:
                        event_count += 1

                        # Log event type
                        logger.debug(f"[TemporalStreamingModel] Event {event_count}: {type(event).__name__}")

                        # Handle different event types using isinstance for type safety
                        if isinstance(event, ResponseOutputItemAddedEvent):
                            # New output item (reasoning, function call, or message)
                            item = getattr(event, 'item', None)
                            output_index = getattr(event, 'output_index', 0)

                            if item and getattr(item, 'type', None) == 'reasoning':
                                logger.debug(f"[TemporalStreamingModel] Starting reasoning item")
                                if not reasoning_context:
                                    # Start a reasoning context for streaming reasoning to UI
                                    reasoning_context = await adk.streaming.streaming_task_message_context(
                                        task_id=task_id,
                                        initial_content=ReasoningContent(
                                            author="agent",
                                            summary=[],
                                            content=[],
                                            type="reasoning",
                                            style="active",
                                        ),
                                    ).__aenter__()
                            elif item and getattr(item, 'type', None) == 'function_call':
                                # Track the function call being streamed
                                function_calls_in_progress[output_index] = {
                                    'id': getattr(item, 'id', ''),
                                    'call_id': getattr(item, 'call_id', ''),
                                    'name': getattr(item, 'name', ''),
                                    'arguments': getattr(item, 'arguments', ''),
                                }
                                logger.debug(f"[TemporalStreamingModel] Starting function call: {item.name}")

                        elif isinstance(event, ResponseFunctionCallArgumentsDeltaEvent):
                            # Stream function call arguments
                            output_index = getattr(event, 'output_index', 0)
                            delta = getattr(event, 'delta', '')

                            if output_index in function_calls_in_progress:
                                function_calls_in_progress[output_index]['arguments'] += delta
                                logger.debug(f"[TemporalStreamingModel] Function call args delta: {delta[:50]}...")

                        elif isinstance(event, ResponseFunctionCallArgumentsDoneEvent):
                            # Function call arguments complete
                            output_index = getattr(event, 'output_index', 0)
                            arguments = getattr(event, 'arguments', '')

                            if output_index in function_calls_in_progress:
                                function_calls_in_progress[output_index]['arguments'] = arguments
                                logger.debug(f"[TemporalStreamingModel] Function call args done")

                        elif isinstance(event, (ResponseReasoningTextDeltaEvent, ResponseReasoningSummaryTextDeltaEvent, ResponseTextDeltaEvent)):
                            # Handle text streaming
                            delta = getattr(event, 'delta', '')

                            if isinstance(event, ResponseReasoningSummaryTextDeltaEvent) and reasoning_context:
                                # Stream reasoning summary deltas - these are the actual reasoning tokens!
                                try:
                                    # Use ReasoningSummaryDelta for reasoning summaries
                                    summary_index = getattr(event, 'summary_index', 0)
                                    delta_obj = ReasoningSummaryDelta(
                                        summary_index=summary_index,
                                        summary_delta=delta,
                                        type="reasoning_summary",
                                    )
                                    update = StreamTaskMessageDelta(
                                        parent_task_message=reasoning_context.task_message,
                                        delta=delta_obj,
                                        type="delta",
                                    )
                                    await reasoning_context.stream_update(update)
                                    # Accumulate the reasoning summary
                                    if len(reasoning_summaries) <= summary_index:
                                        reasoning_summaries.extend([""] * (summary_index + 1 - len(reasoning_summaries)))
                                    reasoning_summaries[summary_index] += delta
                                    logger.debug(f"[TemporalStreamingModel] Streamed reasoning summary: {delta[:30]}..." if len(delta) > 30 else f"[TemporalStreamingModel] Streamed reasoning summary: {delta}")
                                except Exception as e:
                                    logger.warning(f"Failed to send reasoning delta: {e}")
                            elif isinstance(event, ResponseReasoningTextDeltaEvent) and reasoning_context:
                                # Regular reasoning delta (if these ever appear)
                                try:
                                    delta_obj = ReasoningContentDelta(
                                        content_index=0,
                                        content_delta=delta,
                                        type="reasoning_content",
                                    )
                                    update = StreamTaskMessageDelta(
                                        parent_task_message=reasoning_context.task_message,
                                        delta=delta_obj,
                                        type="delta",
                                    )
                                    await reasoning_context.stream_update(update)
                                    reasoning_contents.append(delta)
                                except Exception as e:
                                    logger.warning(f"Failed to send reasoning delta: {e}")
                            elif isinstance(event, ResponseTextDeltaEvent):
                                # Stream regular text output
                                current_text += delta
                                try:
                                    delta_obj = TextDelta(
                                        type="text",
                                        text_delta=delta,
                                    )
                                    update = StreamTaskMessageDelta(
                                        parent_task_message=streaming_context.task_message,
                                        delta=delta_obj,
                                        type="delta",
                                    )
                                    await streaming_context.stream_update(update)
                                except Exception as e:
                                    logger.warning(f"Failed to send text delta: {e}")

                        elif isinstance(event, ResponseOutputItemDoneEvent):
                            # Output item completed
                            item = getattr(event, 'item', None)
                            output_index = getattr(event, 'output_index', 0)

                            if item and getattr(item, 'type', None) == 'reasoning':
                                logger.debug(f"[TemporalStreamingModel] Reasoning item completed")
                                # Don't close the context here - let it stay open for more reasoning events
                                # It will be closed when we send the final update or at the end
                            elif item and getattr(item, 'type', None) == 'function_call':
                                # Function call completed - add to output
                                if output_index in function_calls_in_progress:
                                    call_data = function_calls_in_progress[output_index]
                                    logger.debug(f"[TemporalStreamingModel] Function call completed: {call_data['name']}")

                                    # Create proper function call object
                                    tool_call = ResponseFunctionToolCall(
                                        id=call_data['id'],
                                        call_id=call_data['call_id'],
                                        type="function_call",
                                        name=call_data['name'],
                                        arguments=call_data['arguments'],
                                    )
                                    output_items.append(tool_call)

                        elif isinstance(event, ResponseReasoningSummaryPartAddedEvent):
                            # New reasoning part/summary started - reset accumulator
                            part = getattr(event, 'part', None)
                            if part:
                                part_type = getattr(part, 'type', 'unknown')
                                logger.debug(f"[TemporalStreamingModel] New reasoning part: type={part_type}")
                                # Reset the current reasoning summary for this new part
                                current_reasoning_summary = ""

                        elif isinstance(event, ResponseReasoningSummaryPartDoneEvent):
                            # Reasoning part completed - send final update and close if this is the last part
                            if reasoning_context and reasoning_summaries:
                                logger.debug(f"[TemporalStreamingModel] Reasoning part completed, sending final update")
                                try:
                                    # Send a full message update with the complete reasoning content
                                    complete_reasoning_content = ReasoningContent(
                                        author="agent",
                                        summary=reasoning_summaries,  # Use accumulated summaries
                                        content=reasoning_contents if reasoning_contents else [],
                                        type="reasoning",
                                        style="static",
                                    )

                                    await reasoning_context.stream_update(
                                        update=StreamTaskMessageFull(
                                            parent_task_message=reasoning_context.task_message,
                                            content=complete_reasoning_content,
                                            type="full",
                                        ),
                                    )

                                    # Close the reasoning context after sending the final update
                                    # This matches the reference implementation pattern
                                    await reasoning_context.close()
                                    reasoning_context = None
                                    logger.debug(f"[TemporalStreamingModel] Closed reasoning context after final update")
                                except Exception as e:
                                    logger.warning(f"Failed to send reasoning part done update: {e}")

                        elif isinstance(event, ResponseCompletedEvent):
                            # Response completed
                            logger.debug(f"[TemporalStreamingModel] Response completed")
                            response = getattr(event, 'response', None)
                            if response and hasattr(response, 'output'):
                                # Use the final output from the response
                                output_items = response.output
                                logger.debug(f"[TemporalStreamingModel] Found {len(output_items)} output items in final response")

                    # End of event processing loop - close any open contexts
                    if reasoning_context:
                        await reasoning_context.close()
                        reasoning_context = None

                # Build the response from output items collected during streaming
                # Create output from the items we collected
                response_output = []

                # Process output items from the response
                if output_items:
                    for item in output_items:
                        if isinstance(item, ResponseFunctionToolCall):
                            response_output.append(item)
                        elif isinstance(item, ResponseOutputMessage):
                            response_output.append(item)
                        else:
                            response_output.append(item)
                else:
                    # No output items - create empty message
                    message = ResponseOutputMessage(
                        id=f"msg_{uuid.uuid4().hex[:8]}",
                        type="message",
                        status="completed",
                        role="assistant",
                        content=[ResponseOutputText(
                            type="output_text",
                            text=current_text if current_text else "",
                            annotations=[]
                        )]
                    )
                    response_output.append(message)

                # Create usage object
                usage = Usage(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    input_tokens_details=InputTokensDetails(cached_tokens=0),
                    output_tokens_details=OutputTokensDetails(reasoning_tokens=len(''.join(reasoning_contents)) // 4),  # Approximate
                )

                # Return the response
                return ModelResponse(
                    output=response_output,
                    usage=usage,
                    response_id=f"resp_{uuid.uuid4().hex[:8]}",
                )

            except Exception as e:
                logger.error(f"Error using Responses API: {e}")
                raise

    # The _get_response_with_responses_api method has been merged into get_response above
    # All Responses API logic is now integrated directly in get_response() method

    @override
    def stream_response(self, *args, **kwargs):
        """Streaming is not implemented as we use the async get_response method.
        This method is included for compatibility with the Model interface but should not be used.
        All streaming is handled through the async get_response method with the Responses API."""
        raise NotImplementedError("stream_response is not used in Temporal activities - use get_response instead")


class TemporalStreamingModelProvider(ModelProvider):
    """Custom model provider that returns a streaming-capable model."""

    def __init__(self):
        """Initialize the provider."""
        super().__init__()
        logger.info("[TemporalStreamingModelProvider] Initialized")

    @override
    def get_model(self, model_name: Union[str, None]) -> Model:
        """Get a model instance with streaming capabilities.

        Args:
            model_name: The name of the model to retrieve

        Returns:
            A Model instance with streaming support.
        """
        # Use the provided model_name or default to gpt-4o
        actual_model = model_name if model_name else "gpt-4o"
        logger.info(f"[TemporalStreamingModelProvider] Creating TemporalStreamingModel for model_name: {actual_model}")
        model = TemporalStreamingModel(model_name=actual_model)
        return model
