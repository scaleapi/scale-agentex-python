import asyncio

from project.workflow import At030CustomActivitiesWorkflow
from agentex.lib.utils.debug import setup_debug_if_enabled
from project.custom_activites import CustomActivities
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

    # Create a worker with automatic tracing
    worker = AgentexWorker(
        task_queue=task_queue_name,
    )

    agentex_activities = get_all_activities()

    custom_activities_use_case = CustomActivities()
    all_activites = [
        custom_activities_use_case.report_progress, 
        custom_activities_use_case.process_batch_events,
        *agentex_activities, 
    ]

    await worker.run(
        activities=all_activites,
        workflow=At030CustomActivitiesWorkflow,
    )

if __name__ == "__main__":
    asyncio.run(main()) 