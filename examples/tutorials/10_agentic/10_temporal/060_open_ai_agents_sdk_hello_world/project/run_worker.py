import asyncio

from temporalio.contrib.openai_agents import OpenAIAgentsPlugin

from project.workflow import ExampleTutorialWorkflow
from agentex.lib.utils.debug import setup_debug_if_enabled
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.activities import get_all_activities
from agentex.lib.core.temporal.workers.worker import AgentexWorker

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
    
    # Create a worker with automatic tracing
    # We are also adding the Open AI Agents SDK plugin to the worker.
    worker = AgentexWorker(
        task_queue=task_queue_name,
        plugins=[OpenAIAgentsPlugin()]
    )

    await worker.run(
        activities=all_activities,
        workflow=ExampleTutorialWorkflow,
    )

if __name__ == "__main__":
    asyncio.run(main()) 