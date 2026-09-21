import asyncio
from datetime import timedelta

from temporalio.contrib.openai_agents import OpenAIAgentsPlugin, ModelActivityParameters
from agents.extensions.models.litellm_provider import LitellmProvider

from project.workflow import At100GeminiLitellmWorkflow
from agentex.lib.utils.debug import setup_debug_if_enabled
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.activities import get_all_activities
from agentex.lib.core.temporal.workers.worker import AgentexWorker
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
    all_activities = get_all_activities() + []  # add your own activities here

    # ============================================================================
    # LITELLM SETUP: Interceptor + LitellmProvider
    # ============================================================================
    # The ContextInterceptor threads task_id through activity headers using
    # Temporal's interceptor pattern. This enables runtime context without
    # forking the Temporal plugin.
    #
    # We use LitellmProvider instead of TemporalStreamingModelProvider to
    # enable routing to Gemini and other models through LiteLLM.
    context_interceptor = ContextInterceptor()

    # Create a worker with automatic tracing
    # IMPORTANT: We use the STANDARD temporalio.contrib.openai_agents.OpenAIAgentsPlugin
    # but with LitellmProvider to handle model routing to Gemini.
    worker = AgentexWorker(
        task_queue=task_queue_name,
        plugins=[OpenAIAgentsPlugin(
            model_params=ModelActivityParameters(
                start_to_close_timeout=timedelta(days=1)
            ),
            model_provider=LitellmProvider(),
        )],
        interceptors=[context_interceptor]
    )

    await worker.run(
        activities=all_activities,
        workflow=At100GeminiLitellmWorkflow,
    )

if __name__ == "__main__":
    asyncio.run(main())
