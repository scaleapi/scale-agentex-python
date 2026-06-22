"""Temporal worker for the Claude Code tutorial.

Run as a separate long-lived process alongside the ACP HTTP server. The
worker polls Temporal for workflow + activity tasks and executes them.

Claude Code does not register custom activities here -- subprocess spawning
happens directly in the workflow signal handler (workflow code) to keep
the tutorial minimal. The built-in Agentex activities (state, messages,
streaming, tracing) are registered via ``get_all_activities()``.

For production use, move the subprocess spawn into a custom activity so
it gets Temporal's retry + timeout guarantees.
"""

import asyncio

from project.workflow import At140ClaudeCodeWorkflow
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
        workflow=At140ClaudeCodeWorkflow,
    )


if __name__ == "__main__":
    asyncio.run(main())
