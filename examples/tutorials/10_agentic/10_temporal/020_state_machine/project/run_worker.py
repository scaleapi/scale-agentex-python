import asyncio
import os

from agentex.lib.core.temporal.activities import get_all_activities
from agentex.lib.core.temporal.workers.worker import AgentexWorker
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables

from workflow import At020StateMachineWorkflow


environment_variables = EnvironmentVariables.refresh()

logger = make_logger(__name__)


async def main():
    task_queue_name = environment_variables.WORKFLOW_TASK_QUEUE
    if task_queue_name is None:
        raise ValueError("WORKFLOW_TASK_QUEUE is not set")

    # Create a worker with automatic tracing
    worker = AgentexWorker(
        task_queue=task_queue_name,
    )

    await worker.run(
        activities=get_all_activities(),
        workflow=At020StateMachineWorkflow,
    )

if __name__ == "__main__":
    asyncio.run(main()) 