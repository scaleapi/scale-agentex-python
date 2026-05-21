"""Temporal worker for the Pydantic AI tutorial.

Run as a separate long-lived process alongside the ACP HTTP server. The
worker polls Temporal for workflow + activity tasks and executes them.

The ``PydanticAIPlugin`` reads ``__pydantic_ai_agents__`` off the workflow
class and registers every model/tool activity the TemporalAgent needs —
so we don't have to enumerate activities by hand here.
"""

import asyncio

from pydantic_ai.durable_exec.temporal import PydanticAIPlugin

from project.workflow import At110PydanticAiWorkflow
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

    # get_all_activities() returns the built-in Agentex activities (state,
    # messages, streaming, tracing). Pydantic AI's TemporalAgent activities
    # are auto-registered by PydanticAIPlugin via __pydantic_ai_agents__.
    worker = AgentexWorker(
        task_queue=task_queue_name,
        plugins=[PydanticAIPlugin()],
    )

    await worker.run(
        activities=get_all_activities(),
        workflow=At110PydanticAiWorkflow,
    )


if __name__ == "__main__":
    asyncio.run(main())
