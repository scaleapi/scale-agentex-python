"""Temporal-aware tracing model provider.

This module provides model implementations that add AgentEx tracing to standard OpenAI models
when running in Temporal workflows/activities. It uses context variables set by the Temporal
context interceptor to access task_id, trace_id, and parent_span_id.

The key innovation is that these are thin wrappers around the standard OpenAI models,
avoiding code duplication while adding tracing capabilities.
"""

import logging
from typing import List, Union, Optional, override

from agents import (
    Tool,
    Model,
    Handoff,
    ModelTracing,
    ModelResponse,
    ModelSettings,
    OpenAIProvider,
    TResponseInputItem,
    AgentOutputSchemaBase,
)
from openai.types.responses import ResponsePromptParam
from agents.models.openai_responses import OpenAIResponsesModel
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from agentex.lib.core.tracing.tracer import AsyncTracer

# Import AgentEx components
from agentex.lib.adk.utils._modules.client import create_async_agentex_client

# Import context variables from the interceptor
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import (
    streaming_task_id,
    streaming_trace_id,
    streaming_parent_span_id,
)

logger = logging.getLogger("agentex.temporal.tracing")


class TemporalTracingModelProvider(OpenAIProvider):
    """Model provider that returns OpenAI models wrapped with AgentEx tracing.

    This provider extends the standard OpenAIProvider to return models that add
    tracing spans around model calls when running in Temporal activities with
    the context interceptor enabled.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the tracing model provider.

        Accepts all the same arguments as OpenAIProvider.
        """
        super().__init__(*args, **kwargs)

        # Initialize tracer for all models
        agentex_client = create_async_agentex_client()
        self._tracer = AsyncTracer(agentex_client)
        logger.info("[TemporalTracingModelProvider] Initialized with AgentEx tracer")

    @override
    def get_model(self, model_name: Optional[str]) -> Model:
        """Get a model wrapped with tracing capabilities.

        Args:
            model_name: The name of the model to use

        Returns:
            A model instance wrapped with tracing
        """
        # Get the base model from the parent provider
        base_model = super().get_model(model_name)

        # Wrap with appropriate tracing wrapper based on model type
        if isinstance(base_model, OpenAIResponsesModel):
            logger.info(f"[TemporalTracingModelProvider] Wrapping OpenAIResponsesModel '{model_name}' with tracing")
            return TemporalTracingResponsesModel(base_model, self._tracer)  # type: ignore[abstract]
        elif isinstance(base_model, OpenAIChatCompletionsModel):
            logger.info(f"[TemporalTracingModelProvider] Wrapping OpenAIChatCompletionsModel '{model_name}' with tracing")
            return TemporalTracingChatCompletionsModel(base_model, self._tracer)  # type: ignore[abstract]
        else:
            logger.warning(f"[TemporalTracingModelProvider] Unknown model type, returning without tracing: {type(base_model)}")
            return base_model


class TemporalTracingResponsesModel(Model):
    """Wrapper for OpenAIResponsesModel that adds AgentEx tracing.

    This is a thin wrapper that adds tracing spans around the base model's
    get_response() method. It reads tracing context from ContextVars set by
    the Temporal context interceptor.
    """

    def __init__(self, base_model: OpenAIResponsesModel, tracer: AsyncTracer):
        """Initialize the tracing wrapper.

        Args:
            base_model: The OpenAI Responses model to wrap
            tracer: The AgentEx tracer to use
        """
        self._base_model = base_model
        self._tracer = tracer
        # Expose the model name for compatibility
        self.model = base_model.model

    @override
    async def get_response(
        self,
        system_instructions: Optional[str],
        input: Union[str, List[TResponseInputItem]],
        model_settings: ModelSettings,
        tools: List[Tool],
        output_schema: Optional[AgentOutputSchemaBase],
        handoffs: List[Handoff],
        tracing: ModelTracing,
        previous_response_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        prompt: Optional[ResponsePromptParam] = None,
        **kwargs,
    ) -> ModelResponse:
        """Get a response from the model with optional tracing.

        If tracing context is available from the interceptor, this wraps the
        model call in a tracing span. Otherwise, it passes through to the
        base model without tracing.
        """
        # Try to get tracing context from ContextVars
        task_id = streaming_task_id.get()
        trace_id = streaming_trace_id.get()
        parent_span_id = streaming_parent_span_id.get()

        # If we have tracing context, wrap with span
        if trace_id and parent_span_id:
            logger.debug(f"[TemporalTracingResponsesModel] Adding tracing span for task_id={task_id}, trace_id={trace_id}")

            trace = self._tracer.trace(trace_id)

            async with trace.span(
                parent_id=parent_span_id,
                name="model_get_response",
                input={
                    "model": str(self.model),
                    "has_system_instructions": system_instructions is not None,
                    "input_type": type(input).__name__,
                    "tools_count": len(tools) if tools else 0,
                    "handoffs_count": len(handoffs) if handoffs else 0,
                    "has_output_schema": output_schema is not None,
                    "model_settings": {
                        "temperature": model_settings.temperature,
                        "max_tokens": model_settings.max_tokens,
                        "reasoning": model_settings.reasoning,
                    } if model_settings else None,
                },
            ) as span:
                try:
                    # Call the base model
                    response = await self._base_model.get_response(
                        system_instructions=system_instructions,
                        input=input,
                        model_settings=model_settings,
                        tools=tools,
                        output_schema=output_schema,
                        handoffs=handoffs,
                        tracing=tracing,
                        previous_response_id=previous_response_id,
                        conversation_id=conversation_id,  # type: ignore[call-arg]
                        prompt=prompt,
                        **kwargs,
                    )

                    # Add response info to span output
                    span.output = {  # type: ignore[attr-defined]
                        "response_id": getattr(response, "id", None),
                        "model_used": getattr(response, "model", None),
                        "usage": {
                            "input_tokens": response.usage.input_tokens if response.usage else None,
                            "output_tokens": response.usage.output_tokens if response.usage else None,
                            "total_tokens": response.usage.total_tokens if response.usage else None,
                        } if response.usage else None,
                    }

                    return response

                except Exception as e:
                    # Record error in span
                    span.error = str(e)  # type: ignore[attr-defined]
                    raise
        else:
            # No tracing context, just pass through
            logger.debug("[TemporalTracingResponsesModel] No tracing context available, calling base model directly")
            return await self._base_model.get_response(
                system_instructions=system_instructions,
                input=input,
                model_settings=model_settings,
                tools=tools,
                output_schema=output_schema,
                handoffs=handoffs,
                tracing=tracing,
                previous_response_id=previous_response_id,
                conversation_id=conversation_id,  # type: ignore[call-arg]
                prompt=prompt,
                **kwargs,
            )


class TemporalTracingChatCompletionsModel(Model):
    """Wrapper for OpenAIChatCompletionsModel that adds AgentEx tracing.

    This is a thin wrapper that adds tracing spans around the base model's
    get_response() method. It reads tracing context from ContextVars set by
    the Temporal context interceptor.
    """

    def __init__(self, base_model: OpenAIChatCompletionsModel, tracer: AsyncTracer):
        """Initialize the tracing wrapper.

        Args:
            base_model: The OpenAI ChatCompletions model to wrap
            tracer: The AgentEx tracer to use
        """
        self._base_model = base_model
        self._tracer = tracer
        # Expose the model name for compatibility
        self.model = base_model.model

    @override
    async def get_response(
        self,
        system_instructions: Optional[str],
        input: Union[str, List[TResponseInputItem]],
        model_settings: ModelSettings,
        tools: List[Tool],
        output_schema: Optional[AgentOutputSchemaBase],
        handoffs: List[Handoff],
        tracing: ModelTracing,
        **kwargs,
    ) -> ModelResponse:
        """Get a response from the model with optional tracing.

        If tracing context is available from the interceptor, this wraps the
        model call in a tracing span. Otherwise, it passes through to the
        base model without tracing.
        """
        # Try to get tracing context from ContextVars
        task_id = streaming_task_id.get()
        trace_id = streaming_trace_id.get()
        parent_span_id = streaming_parent_span_id.get()

        # If we have tracing context, wrap with span
        if trace_id and parent_span_id:
            logger.debug(f"[TemporalTracingChatCompletionsModel] Adding tracing span for task_id={task_id}, trace_id={trace_id}")

            trace = self._tracer.trace(trace_id)

            async with trace.span(
                parent_id=parent_span_id,
                name="model_get_response",
                input={
                    "model": str(self.model),
                    "has_system_instructions": system_instructions is not None,
                    "input_type": type(input).__name__,
                    "tools_count": len(tools) if tools else 0,
                    "handoffs_count": len(handoffs) if handoffs else 0,
                    "has_output_schema": output_schema is not None,
                    "model_settings": {
                        "temperature": model_settings.temperature,
                        "max_tokens": model_settings.max_tokens,
                    } if model_settings else None,
                },
            ) as span:
                try:
                    # Call the base model
                    response = await self._base_model.get_response(
                        system_instructions=system_instructions,
                        input=input,
                        model_settings=model_settings,
                        tools=tools,
                        output_schema=output_schema,
                        handoffs=handoffs,
                        tracing=tracing,
                        **kwargs,
                    )

                    # Add response info to span output
                    span.output = {  # type: ignore[attr-defined]
                        "response_id": getattr(response, "id", None),
                        "model_used": getattr(response, "model", None),
                        "usage": {
                            "input_tokens": response.usage.input_tokens if response.usage else None,
                            "output_tokens": response.usage.output_tokens if response.usage else None,
                            "total_tokens": response.usage.total_tokens if response.usage else None,
                        } if response.usage else None,
                    }

                    return response

                except Exception as e:
                    # Record error in span
                    span.error = str(e)  # type: ignore[attr-defined]
                    raise
        else:
            # No tracing context, just pass through
            logger.debug("[TemporalTracingChatCompletionsModel] No tracing context available, calling base model directly")
            return await self._base_model.get_response(
                system_instructions=system_instructions,
                input=input,
                model_settings=model_settings,
                tools=tools,
                output_schema=output_schema,
                handoffs=handoffs,
                tracing=tracing,
                **kwargs,
            )