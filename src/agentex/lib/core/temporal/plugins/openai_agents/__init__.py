"""OpenAI Agents SDK Temporal Plugin with Streaming Support.

This module provides streaming capabilities for the OpenAI Agents SDK in Temporal
using interceptors to thread task_id through workflows to activities.

The streaming implementation works by:
1. Using Temporal interceptors to thread task_id through the execution
2. Streaming LLM responses to Redis in real-time from activities
3. Streaming lifecycle events (tool calls, handoffs) via hooks and activities
4. Returning complete responses to maintain Temporal determinism

Example - Complete Setup:
    >>> from agentex.lib.core.temporal.plugins.openai_agents import (
    ...     StreamingModelProvider,
    ...     TemporalStreamingHooks,
    ...     ContextInterceptor,
    ... )
    >>> from temporalio.contrib.openai_agents import OpenAIAgentsPlugin, ModelActivityParameters
    >>> from datetime import timedelta
    >>> from agents import Agent, Runner
    >>>
    >>> # 1. Create streaming model provider
    >>> model_provider = StreamingModelProvider()
    >>>
    >>> # 2. Create STANDARD plugin with streaming model provider
    >>> plugin = OpenAIAgentsPlugin(
    ...     model_params=ModelActivityParameters(
    ...         start_to_close_timeout=timedelta(seconds=120),
    ...     ),
    ...     model_provider=model_provider,
    ... )
    >>>
    >>> # 3. Register interceptor with worker
    >>> interceptor = ContextInterceptor()
    >>> # Add interceptor to worker configuration
    >>>
    >>> # 4. In workflow, store task_id in instance variable
    >>> self._task_id = params.task.id
    >>>
    >>> # 5. Create hooks for streaming lifecycle events
    >>> hooks = TemporalStreamingHooks(task_id="your-task-id")
    >>>
    >>> # 6. Run agent - interceptor handles task_id threading automatically
    >>> result = await Runner.run(agent, input, hooks=hooks)

This gives you:
- Real-time streaming of LLM responses (via StreamingModel + interceptors)
- Real-time streaming of tool calls (via TemporalStreamingHooks)
- Real-time streaming of agent handoffs (via TemporalStreamingHooks)
- Full Temporal durability and observability
- No forked plugin required - uses standard OpenAIAgentsPlugin
"""

from agentex.lib.core.temporal.plugins.openai_agents.hooks.hooks import (
    TemporalStreamingHooks,
)
from agentex.lib.core.temporal.plugins.openai_agents.hooks.activities import (
    stream_lifecycle_content,
)
from agentex.lib.core.temporal.plugins.openai_agents.models.temporal_tracing_model import (
    TemporalTracingModelProvider,
)
from agentex.lib.core.temporal.plugins.openai_agents.models.temporal_streaming_model import (
    TemporalStreamingModel,
    TemporalStreamingModelProvider,
)
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import (
    ContextInterceptor,
    streaming_task_id,
    streaming_trace_id,
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