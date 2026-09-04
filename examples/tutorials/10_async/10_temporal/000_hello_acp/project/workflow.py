import json
from typing import override

from temporalio import workflow

from agentex.lib import adk
from agentex.lib.types.acp import SendEventParams, CreateTaskParams
from agentex.lib.utils.logging import make_logger
from agentex.types.text_content import TextContent
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow

environment_variables = EnvironmentVariables.refresh()

if environment_variables.WORKFLOW_NAME is None:
    raise ValueError("Environment variable WORKFLOW_NAME is not set")

if environment_variables.AGENT_NAME is None:
    raise ValueError("Environment variable AGENT_NAME is not set")

logger = make_logger(__name__)

@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class At000HelloAcpWorkflow(BaseWorkflow):
    """
    Minimal async workflow template for AgentEx Temporal agents.
    """
    def __init__(self):
        super().__init__(display_name=environment_variables.AGENT_NAME)
        self._complete_task = False

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    @override
    async def on_task_event_send(self, params: SendEventParams) -> None:
        logger.info(f"Received task message instruction: {params}")

        # 2. Echo back the client's message to show it in the UI. This is not done by default so the agent developer has full control over what is shown to the user.
        await adk.messages.create(task_id=params.task.id, content=params.event.content)

        # 3. Send a simple response message.
        # In future tutorials, this is where we'll add more sophisticated response logic.
        await adk.messages.create(
            task_id=params.task.id,
            content=TextContent(
                author="agent",
                content=f"Hello! I've received your message. I can't respond right now, but in future tutorials we'll see how you can get me to intelligently respond to your message.",
            ),
        )

    @workflow.run
    @override
    async def on_task_create(self, params: CreateTaskParams) -> None:
        logger.info(f"Received task create params: {params}")

        # 1. Acknowledge that the task has been created. Gate this one-time prologue
        # on is_continued_run(): run_until_complete below recycles the workflow via
        # continue-as-new, which re-enters on_task_create from the top — without this
        # guard the "you should only see this once" welcome would re-fire on every
        # recycle. Original run -> emit; continued (recycled) run -> skip.
        if not self.is_continued_run():
            await adk.messages.create(
                task_id=params.task.id,
                content=TextContent(
                    author="agent",
                    content=f"Hello! I've received your task. Normally you can do some state initialization here, or just pass and do nothing until you get your first event. For now I'm just acknowledging that I've received a task with the following params:\n\n{json.dumps(params.params, indent=2)}.\n\nYou should only see this message once, when the task is created. All subsequent events will be handled by the `on_task_event_send` handler.",
                ),
            )

        # 2. Keep the workflow open to field events. We use run_until_complete
        # instead of a bare wait_condition: it still waits indefinitely, but also
        # recycles the Temporal event history via continue-as-new before it hits the
        # ~50k-event / 50MB limit, so this chat can stay open forever. Adopting
        # run_until_complete IS the opt-in — agents that keep the old wait_condition
        # never recycle. This agent keeps no cross-turn state, so nothing needs
        # restoring across a recycle and `params` is the only carry-forward. (Agents
        # that DO keep state restore it at the top of @workflow.run on a recycled
        # run — framework-specific, landing per-integration in follow-up PRs.)
        await self.run_until_complete(params, is_complete=lambda: self._complete_task)
