"""
Child Workflow for Human-in-the-Loop Pattern

Child workflow that waits indefinitely for external human input via Temporal signals.
Benefits: Durable waiting, survives system failures, can wait days/weeks without resource consumption.

Usage: External systems send signals to trigger workflow completion.
Production: Replace CLI with web dashboards, mobile apps, or API integrations.
"""

import asyncio

from temporalio import workflow

from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables

environment_variables = EnvironmentVariables.refresh()
logger = make_logger(__name__)


@workflow.defn(name=environment_variables.WORKFLOW_NAME + "_child")
class ChildWorkflow():
    """
    Child workflow that waits for human approval via external signals.
    
    Lifecycle: Spawned by parent → waits for signal → human approves → completes.
    Signal: temporal workflow signal --workflow-id="child-workflow-id" --name="fulfill_order_signal" --input=true
    """

    def __init__(self):
        # Queue to handle signals from external systems (human input)
        self._pending_confirmation: asyncio.Queue[bool] = asyncio.Queue()

    @workflow.run
    async def on_task_create(self, name: str) -> str:
        """
        Wait indefinitely for human approval signal.
        
        Uses workflow.wait_condition() to pause until external signal received.
        Survives system failures and resumes exactly where it left off.
        """
        logger.info(f"Child workflow started: {name}")

        while True:
            # Wait until human sends approval signal (queue becomes non-empty)
            await workflow.wait_condition(
                lambda: not self._pending_confirmation.empty()
            )

            # Process human input and complete workflow
            while not self._pending_confirmation.empty():
                break

            return "Task completed"

    @workflow.signal
    async def fulfill_order_signal(self, success: bool) -> None:
        """
        Receive human approval decision and trigger workflow completion.
        
        External systems send this signal to provide human input.
        CLI: temporal workflow signal --workflow-id="child-workflow-id" --name="fulfill_order_signal" --input=true
        Production: Use Temporal SDK from web apps, mobile apps, APIs, etc.
        """
        # Add human decision to queue, which triggers wait_condition to resolve
        if success == True:
            await self._pending_confirmation.put(True)
