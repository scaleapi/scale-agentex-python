from __future__ import annotations

from typing import Any
from datetime import timedelta

from temporalio.service import RPCError, RPCStatusCode

from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.protocol.acp import SendEventParams, CreateTaskParams, InterruptTaskParams
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.clients.temporal.types import WorkflowState
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.clients.temporal.temporal_client import TemporalClient
from agentex.lib.core.observability.event_metrics import (
    OUTCOME_DELIVERED,
    OUTCOME_ERROR,
    OUTCOME_NO_LIVE_WORKFLOW,
    record_event_delivery,
)


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
        # None / 0 / negative => no execution timeout (workflow can stay open
        # indefinitely, which long-lived chat/session agents rely on). A positive
        # value bounds the whole continue-as-new chain's wall-clock lifetime.
        timeout_seconds = self._env_vars.WORKFLOW_EXECUTION_TIMEOUT_SECONDS
        execution_timeout = (
            timedelta(seconds=timeout_seconds)
            if timeout_seconds and timeout_seconds > 0
            else None
        )
        return await self._temporal_client.start_workflow(
            workflow=self._env_vars.WORKFLOW_NAME,
            arg=CreateTaskParams(
                agent=agent,
                task=task,
                params=params,
            ),
            id=task.id,
            task_queue=self._env_vars.WORKFLOW_TASK_QUEUE,
            execution_timeout=execution_timeout,
        )

    async def get_state(self, task_id: str) -> WorkflowState:
        """
        Get the task state from the async runtime.
        """
        return await self._temporal_client.get_workflow_status(
            workflow_id=task_id,
        )

    async def send_event(self, agent: Agent, task: Task, event: Event, request: dict | None = None) -> None:
        # event/send is accepted+acked by the ACP server before the signal is
        # attempted, so the only place we learn whether the event actually
        # reached a *running* workflow is here. Record the true delivery outcome
        # (see agentex.events.delivery). Behaviour is unchanged — we still raise.
        try:
            result = await self._temporal_client.send_signal(
                workflow_id=task.id,
                signal=SignalName.RECEIVE_EVENT.value,
                payload=SendEventParams(
                    agent=agent,
                    task=task,
                    event=event,
                    request=request,
                ).model_dump(),
            )
        except RPCError as e:
            # NOT_FOUND == no running workflow to receive the event (task already
            # completed or idle-timed-out). Distinct from unexpected errors so we
            # can measure the "arrived too late" rate separately.
            record_event_delivery(
                OUTCOME_NO_LIVE_WORKFLOW
                if e.status == RPCStatusCode.NOT_FOUND
                else OUTCOME_ERROR
            )
            raise
        except Exception:
            record_event_delivery(OUTCOME_ERROR)
            raise
        record_event_delivery(OUTCOME_DELIVERED)
        return result

    async def interrupt(self, agent: Agent, task: Task, request: dict | None = None) -> None:
        """Forward a task/interrupt to the running workflow as a dedicated signal.

        Non-terminal: unlike ``cancel``/``terminate`` this does NOT tear down the
        workflow. It signals ``interrupt_turn`` so the workflow's ``on_interrupt``
        hook can stop the in-flight turn while leaving the task continuable.
        """
        return await self._temporal_client.send_signal(
            workflow_id=task.id,
            signal=SignalName.INTERRUPT_TURN.value,
            payload=InterruptTaskParams(
                agent=agent,
                task=task,
                request=request,
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
