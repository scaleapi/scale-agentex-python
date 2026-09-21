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
from agents.models.openai_provider import OpenAIProvider

from agentex import AsyncAgentex
from agentex.lib.utils.logging import make_logger
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.lib.core.tracing.lineage import merge_refs_into_data, resolve_refs_from_items

logger = make_logger(__name__)


def _serialize_item(item: Any) -> dict[str, Any]:
    """
    Universal serializer for any item type from OpenAI Agents SDK.

    Uses model_dump() for Pydantic models, otherwise extracts attributes manually.
    Filters out internal Pydantic fields that can't be serialized.
    """
    if hasattr(item, "model_dump"):
        # Pydantic model - use model_dump for proper serialization
        try:
            return item.model_dump(mode="json", exclude_unset=True)
        except Exception:
            # Fallback to dict conversion
            return dict(item) if hasattr(item, "__iter__") else {}
    else:
        # Not a Pydantic model - extract attributes manually
        item_dict = {}
        for attr_name in dir(item):
            if not attr_name.startswith("_") and attr_name not in (
                "model_fields",
                "model_config",
                "model_computed_fields",
            ):
                try:
                    attr_value = getattr(item, attr_name, None)
                    # Skip methods and None values
                    if attr_value is not None and not callable(attr_value):
                        # Convert to JSON-serializable format
                        if hasattr(attr_value, "model_dump"):
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
    """Simple model wrapper that adds logging to stream_response and supports tracing.

    .. deprecated::
        Prefer the unified harness surface for new OpenAI Agents integrations:
        wrap a ``Runner.run_streamed`` result in
        ``agentex.lib.adk._modules._openai_turn.OpenAITurn`` and drive
        delivery + tracing through ``UnifiedEmitter`` (see the
        ``050_openai_agents`` / ``120_openai_agents`` tutorials). This
        per-model tracing wrapper predates the harness and is
        retained only for backwards compatibility; it will be removed in a
        future release. No runtime warning is emitted.
    """

    def __init__(
        self,
        original_model: Model,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        tracer: AsyncTracer | None = None,
    ):
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
                if hasattr(self.original_model, "supports_conversation_id"):
                    kwargs["conversation_id"] = conversation_id

                response = await self.original_model.get_response(**kwargs)

                # Set span output with structured data
                if span and response:
                    new_items = []
                    final_output = None

                    # Extract final output text from response
                    response_final_output = getattr(response, "final_output", None)
                    if response_final_output:
                        final_output = response_final_output

                    # Extract items from the response output
                    response_output = getattr(response, "output", None)
                    if response_output:
                        output_items = response_output if isinstance(response_output, list) else [response_output]

                        for item in output_items:
                            try:
                                item_dict = _serialize_item(item)
                                if item_dict:
                                    new_items.append(item_dict)

                                    # Extract final_output from message type if available
                                    if item_dict.get("type") == "message" and not final_output:
                                        content = item_dict.get("content", [])
                                        if content and isinstance(content, list):
                                            for content_part in content:
                                                if isinstance(content_part, dict) and "text" in content_part:
                                                    final_output = content_part["text"]
                                                    break
                            except Exception as e:
                                logger.warning(f"Failed to serialize item in get_response: {e}")
                                continue

                    span.output = {
                        "new_items": new_items,
                        "final_output": final_output,
                    }
                    lineage_refs = resolve_refs_from_items(new_items)
                    if lineage_refs:
                        span.data = merge_refs_into_data(span.data, lineage_refs)

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
            if hasattr(self.original_model, "supports_conversation_id"):
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
                if hasattr(self.original_model, "supports_conversation_id"):
                    stream_kwargs["conversation_id"] = conversation_id

                # Get the stream response from the original model and yield each event
                stream_response = self.original_model.stream_response(**stream_kwargs)

                # Pass through each event from the original stream and track items
                new_items = []
                final_response_text = ""

                async for event in stream_response:
                    event_type = getattr(event, "type", "no-type")

                    # Handle response.output_item.done events which contain completed items
                    if event_type == "response.output_item.done":
                        item = getattr(event, "item", None)
                        if item is not None:
                            try:
                                item_dict = _serialize_item(item)
                                if item_dict:
                                    new_items.append(item_dict)

                                    # Update final_response_text from message type if available
                                    if item_dict.get("type") == "message":
                                        content = item_dict.get("content", [])
                                        if content and isinstance(content, list):
                                            for content_part in content:
                                                if isinstance(content_part, dict) and "text" in content_part:
                                                    final_response_text = content_part["text"]
                                                    break
                            except Exception as e:
                                logger.warning(f"Failed to serialize item in stream_response: {e}")
                                continue

                    yield event

                # Set span output with structured data including tool calls and final response
                span.output = {
                    "new_items": new_items,
                    "final_output": final_response_text if final_response_text else None,
                }
                lineage_refs = resolve_refs_from_items(new_items)
                if lineage_refs:
                    span.data = merge_refs_into_data(span.data, lineage_refs)
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
            if hasattr(self.original_model, "supports_conversation_id"):
                stream_kwargs["conversation_id"] = conversation_id

            # Get the stream response from the original model and yield each event
            stream_response = self.original_model.stream_response(**stream_kwargs)

            # Pass through each event from the original stream
            async for event in stream_response:
                yield event


class SyncStreamingProvider(OpenAIProvider):
    """Simple OpenAI provider wrapper that adds logging to streaming and supports tracing.

    .. deprecated::
        Prefer the unified harness surface for new OpenAI Agents integrations
        (see :class:`SyncStreamingModel` and the ``OpenAITurn`` +
        ``UnifiedEmitter`` pattern). This provider wrapper predates the harness
        and is retained only for backwards compatibility; it will be removed in
        a future release. No runtime warning is emitted.
    """

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


# The OpenAI streaming tap ``convert_openai_to_agentex_events`` now lives in
# ``agentex.lib.adk._modules._openai_sync``; re-exported here for back-compat.
from agentex.lib.adk._modules._openai_sync import (  # noqa: E402
    convert_openai_to_agentex_events as convert_openai_to_agentex_events,
)
