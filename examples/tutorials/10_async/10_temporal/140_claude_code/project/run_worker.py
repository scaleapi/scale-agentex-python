"""Temporal worker for the Claude Code tutorial.

Run as a separate long-lived process alongside the ACP HTTP server. The
worker polls Temporal for workflow + activity tasks and executes them.

The Claude Code CLI subprocess runs in the ``run_claude_code_turn`` activity
(registered below alongside the built-in Agentex activities), because
subprocess I/O is not permitted on the Temporal workflow event loop.
"""

import asyncio

from project.workflow import At140ClaudeCodeWorkflow
from project.activities import run_claude_code_turn
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
        activities=[run_claude_code_turn, *get_all_activities()],
        workflow=At140ClaudeCodeWorkflow,
    )


if __name__ == "__main__":
    asyncio.run(main())
