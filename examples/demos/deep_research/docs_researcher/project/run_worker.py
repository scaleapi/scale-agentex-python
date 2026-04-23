import asyncio

from datetime import timedelta
from temporalio.contrib.openai_agents import OpenAIAgentsPlugin, ModelActivityParameters

from agentex.lib.core.temporal.activities import get_all_activities
from agentex.lib.core.temporal.workers.worker import AgentexWorker
from agentex.lib.core.temporal.plugins.openai_agents.interceptors.context_interceptor import ContextInterceptor
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables

from project.workflow import DocsResearchWorkflow
from project.activities import web_search, fetch_docs_page

environment_variables = EnvironmentVariables.refresh()

logger = make_logger(__name__)


async def main():
    task_queue_name = environment_variables.WORKFLOW_TASK_QUEUE
    if task_queue_name is None:
        raise ValueError("WORKFLOW_TASK_QUEUE is not set")

    all_activities = get_all_activities() + [web_search, fetch_docs_page]

    context_interceptor = ContextInterceptor()

    model_params = ModelActivityParameters(
        start_to_close_timeout=timedelta(minutes=10),
    )

    worker = AgentexWorker(
        task_queue=task_queue_name,
        plugins=[
            OpenAIAgentsPlugin(
                model_params=model_params,
            ),
        ],
        interceptors=[context_interceptor],
    )

    await worker.run(
        activities=all_activities,
        workflow=DocsResearchWorkflow,
    )


if __name__ == "__main__":
    asyncio.run(main())
