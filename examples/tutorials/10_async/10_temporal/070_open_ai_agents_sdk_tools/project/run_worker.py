import asyncio
from datetime import timedelta

from temporalio.contrib.openai_agents import OpenAIAgentsPlugin, ModelActivityParameters

from project.workflow import ExampleTutorialWorkflow
from project.activities import get_weather, deposit_money, withdraw_money
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
    all_activities = get_all_activities() + [withdraw_money, deposit_money, get_weather]  # add your own activities here
    
    # Create a worker with automatic tracing
    # We are also adding the Open AI Agents SDK plugin to the worker.
    worker = AgentexWorker(
        task_queue=task_queue_name,
        plugins=[OpenAIAgentsPlugin(
            model_params=ModelActivityParameters(
                    start_to_close_timeout=timedelta(days=1)
                )
        )],
    )

    await worker.run(
        activities=all_activities,
        workflow=ExampleTutorialWorkflow,
    )

if __name__ == "__main__":
    asyncio.run(main()) 