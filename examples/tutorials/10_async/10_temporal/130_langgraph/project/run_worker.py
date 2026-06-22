"""Temporal worker for at130-langgraph.

Run as a separate long-lived process alongside the ACP HTTP server. The
worker polls Temporal for workflow + activity tasks and executes them.

The ``LangGraphPlugin`` is given the graph registry (``{ GRAPH_NAME: graph }``).
At runtime it turns the graph's ``execute_in="activity"`` nodes into Temporal
activities and registers them on the worker automatically.
"""

import asyncio

from temporalio.contrib.langgraph import LangGraphPlugin

from project.graph import GRAPH_NAME, build_graph
from project.workflow import AtHarnessLanggraphWorkflow
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

    worker = AgentexWorker(
        task_queue=task_queue_name,
        plugins=[LangGraphPlugin(graphs={GRAPH_NAME: build_graph()})],
    )

    await worker.run(
        activities=get_all_activities(),
        workflow=AtHarnessLanggraphWorkflow,
    )


if __name__ == "__main__":
    asyncio.run(main())
