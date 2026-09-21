import asyncio

from temporalio.contrib.openai_agents import OpenAIAgentsPlugin

from project.workflow import At080OpenAiAgentsSdkHumanInTheLoopWorkflow
from project.activities import confirm_order, deposit_money, withdraw_money
from project.child_workflow import ChildWorkflow
from agentex.lib.utils.debug import setup_debug_if_enabled
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.activities import get_all_activities
from agentex.lib.core.temporal.workers.worker import AgentexWorker
from agentex.lib.core.temporal.plugins.openai_agents.hooks.activities import stream_lifecycle_content
from agentex.lib.core.temporal.plugins.openai_agents.models.temporal_streaming_model import (
    TemporalStreamingModelProvider,
)
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import ContextInterceptor

environment_variables = EnvironmentVariables.refresh()

logger = make_logger(__name__)


async def main():
    # Setup debug mode if enabled
    setup_debug_if_enabled()

    task_queue_name = environment_variables.WORKFLOW_TASK_QUEUE
    if task_queue_name is None:
        raise ValueError("WORKFLOW_TASK_QUEUE is not set")

    # Add activities to the worker
    # stream_lifecycle_content is required for hooks to work (creates tool_request/tool_response messages)
    all_activities = get_all_activities() + [withdraw_money, deposit_money, confirm_order, stream_lifecycle_content]  # add your own activities here

    # ============================================================================
    # STREAMING SETUP: Interceptor + Model Provider
    # ============================================================================
    # This is where the streaming magic is configured! Two key components:
    #
    # 1. ContextInterceptor
    #    - Threads task_id through activity headers using Temporal's interceptor pattern
    #    - Outbound: Reads _task_id from workflow instance, injects into activity headers
    #    - Inbound: Extracts task_id from headers, sets streaming_task_id ContextVar
    #    - This enables runtime context without forking the Temporal plugin!
    #
    # 2. TemporalStreamingModelProvider
    #    - Returns TemporalStreamingModel instances that read task_id from ContextVar
    #    - TemporalStreamingModel.get_response() streams tokens to Redis in real-time
    #    - Still returns complete response to Temporal for determinism/replay safety
    #    - Uses AgentEx ADK streaming infrastructure (Redis XADD to stream:{task_id})
    #
    # Together, these enable real-time LLM streaming while maintaining Temporal's
    # durability guarantees. No forked components - uses STANDARD OpenAIAgentsPlugin!
    context_interceptor = ContextInterceptor()
    temporal_streaming_model_provider = TemporalStreamingModelProvider()

    # Create a worker with automatic tracing
    # IMPORTANT: We use the STANDARD temporalio.contrib.openai_agents.OpenAIAgentsPlugin
    # No forking needed! The interceptor + model provider handle all streaming logic.
    worker = AgentexWorker(
        task_queue=task_queue_name,
        plugins=[OpenAIAgentsPlugin(model_provider=temporal_streaming_model_provider)],
        interceptors=[context_interceptor],
    )

    await worker.run(
        activities=all_activities,
        workflows=[At080OpenAiAgentsSdkHumanInTheLoopWorkflow, ChildWorkflow]
    )

if __name__ == "__main__":
    asyncio.run(main())