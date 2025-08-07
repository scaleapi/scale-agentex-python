import asyncio
from typing import Any, Callable, cast

from project.workflow import At011CustomAgentChatWorkflow
from project.special_run_agent import special_run_agent
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.activities import get_all_activities
from agentex.lib.core.temporal.workers.worker import AgentexWorker


async def main() -> None:
    environment_variables = EnvironmentVariables.refresh()

    if environment_variables is None:
        raise ValueError("Environment variables could not be loaded")

    task_queue_name = environment_variables.WORKFLOW_TASK_QUEUE
    if task_queue_name is None:
        raise ValueError("WORKFLOW_TASK_QUEUE is not set")

    # Create a worker with automatic tracing
    worker = AgentexWorker(
        task_queue=task_queue_name,
    )

    await worker.run(
        activities=cast(Callable[..., list[Callable[..., Any]]], get_all_activities)() + [special_run_agent],
        workflow=At011CustomAgentChatWorkflow,
    )


if __name__ == "__main__":
    asyncio.run(main())
