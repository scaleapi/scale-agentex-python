"""OpenAI Agents SDK Temporal Plugin with Streaming Support.

This module provides streaming capabilities for the OpenAI Agents SDK in Temporal
using interceptors to thread task_id through workflows to activities.

The streaming implementation works by:
1. Using Temporal interceptors to thread task_id through the execution
2. Streaming LLM responses to Redis in real-time from activities
3. Returning complete responses to maintain Temporal determinism

Example:
    >>> from agentex.lib.core.temporal.plugins.openai_agents import (
    ...     TemporalStreamingModelProvider,
    ...     TemporalTracingModelProvider,
    ...     ContextInterceptor,
    ... )
    >>> from temporalio.contrib.openai_agents import OpenAIAgentsPlugin, ModelActivityParameters
    >>> from datetime import timedelta
    >>>
    >>> # Create streaming model provider
    >>> model_provider = TemporalStreamingModelProvider()
    >>>
    >>> # Create STANDARD plugin with streaming model provider
    >>> plugin = OpenAIAgentsPlugin(
    ...     model_params=ModelActivityParameters(
    ...         start_to_close_timeout=timedelta(seconds=120),
    ...     ),
    ...     model_provider=model_provider,
    ... )
    >>>
    >>> # Register interceptor with worker
    >>> interceptor = ContextInterceptor()
    >>> # Add interceptor to worker configuration
"""

from agentex.lib.core.temporal.plugins.openai_agents import (
    ContextInterceptor,
    TemporalStreamingHooks,
    TemporalStreamingModel,
    TemporalTracingModelProvider,
    TemporalStreamingModelProvider,
    streaming_task_id,
    streaming_trace_id,
    stream_lifecycle_content,
    streaming_parent_span_id,
)

__all__ = [
    "TemporalStreamingModel",
    "TemporalStreamingModelProvider",
    "TemporalTracingModelProvider",
    "ContextInterceptor",
    "streaming_task_id",
    "streaming_trace_id",
    "streaming_parent_span_id",
    "TemporalStreamingHooks",
    "stream_lifecycle_content",
]