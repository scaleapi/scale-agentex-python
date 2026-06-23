"""Temporal worker for the OpenAI Agents harness tutorial.

Runs as a separate long-lived process alongside the ACP HTTP server. Registers
the built-in Agentex activities plus the custom harness agent activity
(``HarnessActivities.run_harness_openai_agent``), and the workflow.
"""

import asyncio

from project.workflow import At140HarnessOpenaiWorkflow
from project.activities import HarnessActivities
from agentex.lib.utils.debug import setup_debug_if_enabled
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.activities import get_all_activities
from agentex.lib.core.temporal.workers.worker import AgentexWorker

environment_variables = EnvironmentVariables.refresh()
logger = make_logger(__name__)


async def main():
    setup_debug_if_enabled()

    task_queue_name = environment_variables.WORKFLOW_TASK_QUEUE
    if task_queue_name is None:
        raise ValueError("WORKFLOW_TASK_QUEUE is not set")

    harness_activities = HarnessActivities()
    all_activities = [
        harness_activities.run_harness_openai_agent,
        *get_all_activities(),
    ]

    worker = AgentexWorker(task_queue=task_queue_name)

    await worker.run(
        activities=all_activities,
        workflow=At140HarnessOpenaiWorkflow,
    )


if __name__ == "__main__":
    asyncio.run(main())
