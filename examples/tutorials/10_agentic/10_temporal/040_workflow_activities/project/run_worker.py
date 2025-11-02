import asyncio

from temporalio.contrib.openai_agents import OpenAIAgentsPlugin

from project.workflow import WorkflowActivitiesWorkflow
from project.activities import (
    save_to_database,
    send_notification,
    process_batch,
    generate_report,
)
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

    # ============================================================================
    # REGISTER WORKFLOW ACTIVITIES
    # ============================================================================
    # These are activities for WORKFLOW ORCHESTRATION, not agent tools.
    # The workflow calls these directly to handle:
    # - Database operations
    # - Notifications
    # - Batch processing
    # - Report generation
    #
    # Different from tutorial 020 where activities are used AS agent tools!
    all_activities = get_all_activities() + [
        save_to_database,
        send_notification,
        process_batch,
        generate_report,
        stream_lifecycle_content,
    ]

    # ============================================================================
    # STREAMING SETUP: Interceptor + Model Provider
    # ============================================================================
    # Enable real-time streaming of agent responses
    context_interceptor = ContextInterceptor()
    temporal_streaming_model_provider = TemporalStreamingModelProvider()

    # Create worker with OpenAI Agents SDK plugin
    worker = AgentexWorker(
        task_queue=task_queue_name,
        plugins=[OpenAIAgentsPlugin(model_provider=temporal_streaming_model_provider)],
        interceptors=[context_interceptor],
    )

    await worker.run(
        activities=all_activities,
        workflow=WorkflowActivitiesWorkflow,
    )

if __name__ == "__main__":
    asyncio.run(main())
