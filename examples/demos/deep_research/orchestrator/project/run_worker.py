import asyncio

from datetime import timedelta
from temporalio.contrib.openai_agents import OpenAIAgentsPlugin, ModelActivityParameters

from agentex.lib.core.temporal.activities import get_all_activities
from agentex.lib.core.temporal.workers.worker import AgentexWorker
from agentex.lib.core.temporal.plugins.openai_agents.hooks.activities import stream_lifecycle_content
from agentex.lib.core.temporal.plugins.openai_agents.models.temporal_streaming_model import (
    TemporalStreamingModelProvider,
)
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import ContextInterceptor
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables

from project.workflow import ResearchOrchestratorWorkflow

environment_variables = EnvironmentVariables.refresh()

logger = make_logger(__name__)


async def main():
    task_queue_name = environment_variables.WORKFLOW_TASK_QUEUE
    if task_queue_name is None:
        raise ValueError("WORKFLOW_TASK_QUEUE is not set")

    all_activities = get_all_activities() + [stream_lifecycle_content]

    context_interceptor = ContextInterceptor()
    streaming_model_provider = TemporalStreamingModelProvider()

    model_params = ModelActivityParameters(
        start_to_close_timeout=timedelta(minutes=10),
    )

    worker = AgentexWorker(
        task_queue=task_queue_name,
        plugins=[
            OpenAIAgentsPlugin(
                model_params=model_params,
                model_provider=streaming_model_provider,
            ),
        ],
        interceptors=[context_interceptor],
    )

    await worker.run(
        activities=all_activities,
        workflow=ResearchOrchestratorWorkflow,
    )


if __name__ == "__main__":
    asyncio.run(main())
