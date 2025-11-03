"""Simple OpenAI Provider wrapper that adds logging to demonstrate streaming is working."""

from __future__ import annotations

from typing import Any, Union, Optional, override

from agents import (
    Tool,
    Model,
    Handoff,
    ModelTracing,
    ModelResponse,
    ModelSettings,
    TResponseInputItem,
    AgentOutputSchemaBase,
)
from openai.types.responses import (
    ResponseTextDeltaEvent,
    ResponseFunctionToolCall,
    ResponseFunctionWebSearch,
    ResponseOutputItemDoneEvent,
    ResponseOutputItemAddedEvent,
    ResponseCodeInterpreterToolCall,
    ResponseReasoningSummaryPartDoneEvent,
    ResponseReasoningSummaryPartAddedEvent,
    ResponseReasoningSummaryTextDeltaEvent,
)
from agents.models.openai_provider import OpenAIProvider

from agentex import AsyncAgentex
from agentex.lib.utils.logging import make_logger
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.task_message_content import TextContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent

logger = make_logger(__name__)


def _serialize_item(item: Any) -> dict[str, Any]:
    """
    Universal serializer for any item type from OpenAI Agents SDK.

    Uses model_dump() for Pydantic models, otherwise extracts attributes manually.
    Filters out internal Pydantic fields that can't be serialized.
    """
    if hasattr(item, 'model_dump'):
        # Pydantic model - use model_dump for proper serialization
        try:
            return item.model_dump(mode='json', exclude_unset=True)
        except Exception:
            # Fallback to dict conversion
            return dict(item) if hasattr(item, '__iter__') else {}
    else:
        # Not a Pydantic model - extract attributes manually
        item_dict = {}
        for attr_name in dir(item):
            if not attr_name.startswith('_') and attr_name not in ('model_fields', 'model_config', 'model_computed_fields'):
                try:
                    attr_value = getattr(item, attr_name, None)
                    # Skip methods and None values
                    if attr_value is not None and not callable(attr_value):
                        # Convert to JSON-serializable format
                        if hasattr(attr_value, 'model_dump'):
                            item_dict[attr_name] = attr_value.model_dump()
                        elif isinstance(attr_value, (str, int, float, bool, list, dict)):
                            item_dict[attr_name] = attr_value
                        else:
                            item_dict[attr_name] = str(attr_value)
                except Exception:
                    # Skip attributes that can't be accessed
                    pass
        return item_dict


class SyncStreamingModel(Model):
    """Simple model wrapper that adds logging to stream_response and supports tracing."""

    def __init__(self, original_model: Model, trace_id: str | None = None, parent_span_id: str | None = None, tracer: AsyncTracer | None = None):
        """Initialize with the original OpenAI model to wrap.
        Args:
            original_model: The OpenAI model instance to wrap
            trace_id: Optional trace ID for distributed tracing
            parent_span_id: Optional parent span ID for tracing hierarchy
            tracer: Optional AsyncTracer for distributed tracing
        """
        self.original_model = original_model
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        self.tracer = tracer

    @override
    async def get_response(
        self,
        system_instructions: Optional[str],
        input: Union[str, list[TResponseInputItem]],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: Optional[AgentOutputSchemaBase],
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        prompt: Any = None,
    ) -> ModelResponse:
        """Pass through to the original model's get_response with tracing support."""

        # Wrap the request in a tracing span if tracer is available
        if self.tracer and self.trace_id:
            trace = self.tracer.trace(self.trace_id)
            async with trace.span(
                parent_id=self.parent_span_id,
                name="run_agent",
                input={
                    "system_instructions": system_instructions,
                    "input": input,
                    "model_settings": str(model_settings) if model_settings else None,
                    "tools": [tool.name for tool in tools] if tools else [],
                    "output_schema": str(output_schema) if output_schema else None,
                    "handoffs": [str(h) for h in handoffs] if handoffs else [],
                    "previous_response_id": previous_response_id,
                },
            ) as span:
                # Build kwargs, excluding conversation_id if not supported
                kwargs = {
                    "system_instructions": system_instructions,
                    "input": input,
                    "model_settings": model_settings,
                    "tools": tools,
                    "output_schema": output_schema,
                    "handoffs": handoffs,
                    "tracing": tracing,
                    "previous_response_id": previous_response_id,
                    "prompt": prompt,
                }

                # Only add conversation_id if the model supports it
                if hasattr(self.original_model, 'supports_conversation_id'):
                    kwargs["conversation_id"] = conversation_id

                response = await self.original_model.get_response(**kwargs)

                # Set span output with structured data
                if span and response:
                    new_items = []
                    final_output = None

                    # Extract final output text from response
                    response_final_output = getattr(response, 'final_output', None)
                    if response_final_output:
                        final_output = response_final_output

                    # Extract items from the response output
                    response_output = getattr(response, 'output', None)
                    if response_output:
                        output_items = response_output if isinstance(response_output, list) else [response_output]

                        for item in output_items:
                            item_dict = _serialize_item(item)
                            if item_dict:
                                new_items.append(item_dict)

                                # Extract final_output from message type if available
                                if item_dict.get('type') == 'message' and not final_output:
                                    content = item_dict.get('content', [])
                                    if content and isinstance(content, list):
                                        for content_part in content:
                                            if isinstance(content_part, dict) and 'text' in content_part:
                                                final_output = content_part['text']
                                                break

                    span.output = {
                        "new_items": new_items,
                        "final_output": final_output,
                    }

                return response
        else:
            # No tracing, just call normally
            # Build kwargs, excluding conversation_id if not supported
            kwargs = {
                "system_instructions": system_instructions,
                "input": input,
                "model_settings": model_settings,
                "tools": tools,
                "output_schema": output_schema,
                "handoffs": handoffs,
                "tracing": tracing,
                "previous_response_id": previous_response_id,
                "prompt": prompt,
            }

            # Only add conversation_id if the model supports it
            if hasattr(self.original_model, 'supports_conversation_id'):
                kwargs["conversation_id"] = conversation_id

            return await self.original_model.get_response(**kwargs)

    @override
    async def stream_response(
        self,
        system_instructions: Optional[str],
        input: Union[str, list[TResponseInputItem]],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: Optional[AgentOutputSchemaBase],
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        prompt: Any = None,
    ):  # Return type is generic AsyncIterator for flexibility
        """Wrap the original model's stream_response and pass through OpenAI events.
        This method passes through the OpenAI stream events from the underlying model.
        The conversion to AgentEx types happens in the ACP layer.
        """

        # Wrap the streaming in a tracing span if tracer is available
        if self.tracer and self.trace_id:
            trace = self.tracer.trace(self.trace_id)

            # Manually start the span instead of using context manager
            span = await trace.start_span(
                parent_id=self.parent_span_id,
                name="run_agent_streamed",
                input={
                    "system_instructions": system_instructions,
                    "input": input,
                    "model_settings": str(model_settings) if model_settings else None,
                    "tools": [tool.name for tool in tools] if tools else [],
                    "output_schema": str(output_schema) if output_schema else None,
                    "handoffs": [str(h) for h in handoffs] if handoffs else [],
                    "previous_response_id": previous_response_id,
                },
            )

            try:
                # Get the stream from the original model
                stream_kwargs = {
                    "system_instructions": system_instructions,
                    "input": input,
                    "model_settings": model_settings,
                    "tools": tools,
                    "output_schema": output_schema,
                    "handoffs": handoffs,
                    "tracing": tracing,
                    "previous_response_id": previous_response_id,
                    "prompt": prompt,
                }

                # Only add conversation_id if the model supports it
                if hasattr(self.original_model, 'supports_conversation_id'):
                    stream_kwargs["conversation_id"] = conversation_id

                # Get the stream response from the original model and yield each event
                stream_response = self.original_model.stream_response(**stream_kwargs)

                # Pass through each event from the original stream and track items
                new_items = []
                final_response_text = ""

                async for event in stream_response:
                    event_type = getattr(event, 'type', 'no-type')

                    # Handle response.output_item.done events which contain completed items
                    if event_type == 'response.output_item.done':
                        item = getattr(event, 'item', None)
                        if item is not None:
                            item_dict = _serialize_item(item)
                            if item_dict:
                                new_items.append(item_dict)

                                # Update final_response_text from message type if available
                                if item_dict.get('type') == 'message':
                                    content = item_dict.get('content', [])
                                    if content and isinstance(content, list):
                                        for content_part in content:
                                            if isinstance(content_part, dict) and 'text' in content_part:
                                                final_response_text = content_part['text']
                                                break

                    yield event

                # Set span output with structured data including tool calls and final response
                span.output = {
                    "new_items": new_items,
                    "final_output": final_response_text if final_response_text else None,
                }
            finally:
                # End the span after all events have been yielded
                await trace.end_span(span)
        else:
            # No tracing, just stream normally
            # Get the stream from the original model
            stream_kwargs = {
                "system_instructions": system_instructions,
                "input": input,
                "model_settings": model_settings,
                "tools": tools,
                "output_schema": output_schema,
                "handoffs": handoffs,
                "tracing": tracing,
                "previous_response_id": previous_response_id,
                "prompt": prompt,
            }

            # Only add conversation_id if the model supports it
            if hasattr(self.original_model, 'supports_conversation_id'):
                stream_kwargs["conversation_id"] = conversation_id

            # Get the stream response from the original model and yield each event
            stream_response = self.original_model.stream_response(**stream_kwargs)

            # Pass through each event from the original stream
            async for event in stream_response:
                yield event

class SyncStreamingProvider(OpenAIProvider):
    """Simple OpenAI provider wrapper that adds logging to streaming and supports tracing."""

    def __init__(self, trace_id: str | None = None, parent_span_id: str | None = None, *args, **kwargs):
        """Initialize the provider with tracing support.
        Args:
            trace_id: Optional trace ID for distributed tracing
            parent_span_id: Optional parent span ID for tracing hierarchy
            *args: Additional positional arguments for OpenAIProvider
            **kwargs: Additional keyword arguments for OpenAIProvider
        """
        super().__init__(*args, **kwargs)
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id

        # Initialize AsyncTracer with client directly in the provider
        if trace_id:
            agentex_client = AsyncAgentex()
            self.tracer = AsyncTracer(agentex_client)
        else:
            self.tracer = None

    @override
    def get_model(self, model_name: Optional[str] = None) -> Model:
        """Get a model wrapped with our logging capabilities and tracing.
        Args:
            model_name: The name of the model to retrieve
        Returns:
            A SyncStreamingModel that wraps the original OpenAI model
        """
        # Get the original model from the parent class
        original_model = super().get_model(model_name)

        # Wrap it with our logging capabilities and tracing info
        wrapped_model = SyncStreamingModel(original_model, self.trace_id, self.parent_span_id, self.tracer)

        return wrapped_model


def _extract_tool_call_info(tool_call_item: Any) -> tuple[str, str, dict[str, Any]]:
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

    if isinstance(tool_call_item, ResponseFunctionWebSearch):
        tool_name = "web_search"
        tool_arguments = {"action": tool_call_item.action.model_dump(), "status": tool_call_item.status}
    elif isinstance(tool_call_item, ResponseCodeInterpreterToolCall):
        tool_name = "code_interpreter"
        tool_arguments = {"code": tool_call_item.code, "status": tool_call_item.status}
    elif isinstance(tool_call_item, ResponseFunctionToolCall):
        # Handle standard function tool calls
        tool_name = tool_call_item.name
        # Handle the arguments field which might be a string or None
        if tool_call_item.arguments:
            if isinstance(tool_call_item.arguments, str):
                import json
                tool_arguments = json.loads(tool_call_item.arguments) if tool_call_item.arguments else {}
            else:
                tool_arguments = tool_call_item.arguments
        else:
            tool_arguments = {}
    else:
        # Generic handling for any tool call type
        tool_name = getattr(tool_call_item, "name", type(tool_call_item).__name__)
        # Handle the arguments field which might be a string or None
        if hasattr(tool_call_item, "arguments"):
            arguments = tool_call_item.arguments
            if isinstance(arguments, str):
                import json
                tool_arguments = json.loads(arguments) if arguments else {}
            elif arguments is None:
                tool_arguments = {}
            else:
                tool_arguments = arguments
        else:
            tool_arguments = tool_call_item.model_dump()

    return call_id, tool_name, tool_arguments


def _extract_tool_response_info(tool_map: dict[str, Any], tool_output_item: Any) -> tuple[str, str, str]:
    """
    Extract call_id, tool_name, and content from a tool output item.
    Args:
        tool_map: Dictionary mapping call_ids to tool names
        tool_output_item: The tool output item to process
    Returns:
        A tuple of (call_id, tool_name, content)
    """

    # Handle different formats of tool_output_item
    if isinstance(tool_output_item, dict):
        call_id = tool_output_item.get("call_id", tool_output_item.get("id", f"unknown_call_{id(tool_output_item)}"))
        content = tool_output_item.get("output", str(tool_output_item))
    else:
        # Try to get call_id from attributes
        if hasattr(tool_output_item, "call_id"):
            call_id = tool_output_item.call_id
        elif hasattr(tool_output_item, "id"):
            call_id = tool_output_item.id
        else:
            call_id = f"unknown_call_{id(tool_output_item)}"

        # Get content
        if hasattr(tool_output_item, "output"):
            content = tool_output_item.output
        else:
            content = str(tool_output_item)

    # Get tool name from map
    tool_name = tool_map.get(call_id, "unknown_tool")

    return call_id, tool_name, content


async def convert_openai_to_agentex_events(stream_response):
    """Convert OpenAI streaming events to AgentEx TaskMessageUpdate events.
    This function takes an async iterator of OpenAI events and yields AgentEx
    TaskMessageUpdate events based on the OpenAI event types.
    Args:
        stream_response: An async iterator of OpenAI streaming events
    Yields:
        TaskMessageUpdate: AgentEx streaming events (StreamTaskMessageDelta or StreamTaskMessageDone)
    """

    tool_map = {}
    event_count = 0
    message_index = 0  # Track message index for proper sequencing
    seen_tool_output = False  # Track if we've seen tool output to know when final text starts
    item_id_to_index = {}  # Map item_id to message index
    current_reasoning_summary = ""  # Accumulate reasoning summary text

    async for event in stream_response:
        event_count += 1

        # Check for raw response events which contain the actual OpenAI streaming events
        if hasattr(event, 'type') and event.type == 'raw_response_event':
            if hasattr(event, 'data'):
                raw_event = event.data

                # Check for ResponseOutputItemAddedEvent which signals a new message starting
                if isinstance(raw_event, ResponseOutputItemAddedEvent):
                    # Don't increment here - we'll increment when we see the actual text delta
                    # This is just a signal that a new message is starting
                    pass

                # Handle item completion - send done event to close the message
                elif isinstance(raw_event, ResponseOutputItemDoneEvent):
                    item_id = raw_event.item.id
                    if item_id in item_id_to_index:
                        # Send done event for this message
                        yield StreamTaskMessageDone(
                            type="done",
                            index=item_id_to_index[item_id],
                        )

                # Skip reasoning summary events since o1 reasoning tokens are not accessible
                elif isinstance(raw_event, (ResponseReasoningSummaryPartAddedEvent,
                                            ResponseReasoningSummaryTextDeltaEvent,
                                            ResponseReasoningSummaryPartDoneEvent)):
                    pass

                # Check if this is a text delta event from OpenAI
                elif isinstance(raw_event, ResponseTextDeltaEvent):
                    # Check if this event has an item_id
                    item_id = getattr(raw_event, 'item_id', None)

                    # If this is a new item_id we haven't seen, it's a new message
                    if item_id and item_id not in item_id_to_index:
                        # Check if this is truly a NEW text message after tools
                        # We need to differentiate between the first text and the final text after tools
                        if seen_tool_output:
                            # This is the final text message after tool execution
                            message_index += 1
                            item_id_to_index[item_id] = message_index
                        else:
                            item_id_to_index[item_id] = message_index

                        # Send a start event with empty content for this new text message
                        yield StreamTaskMessageStart(
                            type="start",
                            index=item_id_to_index[item_id],
                            content=TextContent(
                                type="text",
                                author="agent",
                                content="",  # Start with empty content, deltas will fill it
                            ),
                        )

                    # Use the index for this item_id
                    current_index = item_id_to_index.get(item_id, message_index)

                    delta_message = StreamTaskMessageDelta(
                        type="delta",
                        index=current_index,
                        delta=TextDelta(
                            type="text",
                            text_delta=raw_event.delta,
                        ),
                    )
                    yield delta_message

        elif hasattr(event, 'type') and event.type == 'run_item_stream_event':
            # Skip reasoning_item events since o1 reasoning tokens are not accessible via the API
            if hasattr(event, 'item') and event.item.type == 'reasoning_item':
                continue

            # Check for tool_call_item type (this is when a tool is being called)
            elif hasattr(event, 'item') and event.item.type == 'tool_call_item':
                # Extract tool call information using the helper method
                call_id, tool_name, tool_arguments = _extract_tool_call_info(event.item.raw_item)
                tool_map[call_id] = tool_name
                tool_request_content = ToolRequestContent(
                    tool_call_id=call_id,
                    name=tool_name,
                    arguments=tool_arguments,
                    author="agent",
                )
                message_index += 1  # Increment for new message
                yield StreamTaskMessageFull(
                    index=message_index,
                    type="full",
                    content=tool_request_content,
                )

            # Check for tool_call_output_item type (this is when a tool returns output)
            elif hasattr(event, 'item') and event.item.type == 'tool_call_output_item':
                # Extract tool response information using the helper method
                call_id, tool_name, content = _extract_tool_response_info(tool_map, event.item.raw_item)
                tool_response_content = ToolResponseContent(
                    tool_call_id=call_id,
                    name=tool_name,
                    content=content,
                    author="agent",
                )
                message_index += 1  # Increment for new message
                seen_tool_output = True  # Mark that we've seen tool output so next text gets new index
                yield StreamTaskMessageFull(
                    type="full",
                    index=message_index,
                    content=tool_response_content,
                )
