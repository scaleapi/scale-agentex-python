"""Temporal worker for the Codex harness tutorial.

Run as a separate long-lived process alongside the ACP HTTP server. The
worker polls Temporal for workflow + activity tasks and executes them.

Codex subprocess calls happen inside signal handler bodies (not activities),
so no extra activity registrations are needed beyond the standard Agentex set.
"""

import asyncio

from project.workflow import AtHarnessCodexWorkflow
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

    worker = AgentexWorker(task_queue=task_queue_name)

    await worker.run(
        activities=get_all_activities(),
        workflow=AtHarnessCodexWorkflow,
    )


if __name__ == "__main__":
    asyncio.run(main())
