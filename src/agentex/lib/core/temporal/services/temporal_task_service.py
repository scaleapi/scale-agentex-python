from typing import Any
from agentex.lib.core.clients.temporal.temporal_client import TemporalClient
from agentex.lib.core.clients.temporal.types import WorkflowState
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.types.acp import CreateTaskParams
from agentex.lib.types.acp import SendEventParams
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.types.task import Task


class TemporalTaskService:
    """
    Submits Agent agent_tasks to the async runtime for execution.
    """

    def __init__(
        self,
        temporal_client: TemporalClient,
        env_vars: EnvironmentVariables,
    ):
        self._temporal_client = temporal_client
        self._env_vars = env_vars

    async def submit_task(self, agent: Agent, task: Task, params: dict[str, Any] | None) -> str:
        """
        Submit a task to the async runtime for execution.

        returns the workflow ID of the temporal workflow
        """
        return await self._temporal_client.start_workflow(
            workflow=self._env_vars.WORKFLOW_NAME,
            arg=CreateTaskParams(
                agent=agent,
                task=task,
                params=params,
            ),
            id=task.id,
            task_queue=self._env_vars.WORKFLOW_TASK_QUEUE,
        )

    async def get_state(self, task_id: str) -> WorkflowState:
        """
        Get the task state from the async runtime.
        """
        return await self._temporal_client.get_workflow_status(
            workflow_id=task_id,
        )

    async def send_event(self, agent: Agent, task: Task, event: Event) -> None:
        return await self._temporal_client.send_signal(
            workflow_id=task.id,
            signal=SignalName.RECEIVE_EVENT.value,
            payload=SendEventParams(
                agent=agent,
                task=task,
                event=event,
            ).model_dump(),
        )

    async def cancel(self, task_id: str) -> None:
        return await self._temporal_client.cancel_workflow(
            workflow_id=task_id,
        )

    async def terminate(self, task_id: str) -> None:
        return await self._temporal_client.terminate_workflow(
            workflow_id=task_id,
        )
