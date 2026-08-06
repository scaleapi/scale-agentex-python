from __future__ import annotations

from typing import Any, Iterator
from datetime import timedelta
from contextlib import contextmanager

from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.protocol.acp import SendEventParams, CreateTaskParams, InterruptTaskParams
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.clients.temporal.types import WorkflowState
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.clients.temporal.temporal_client import TemporalClient


@contextmanager
def _acp_dispatch_span(name: str, task_id: str | None = None) -> Iterator[None]:
    """Wrap an ACP -> Temporal dispatch (start_workflow / signal) in an OTel span.

    The Temporal OpenTelemetry interceptor propagates trace context by injecting
    the CURRENTLY ACTIVE span into the Temporal message headers on the caller
    side (``start_workflow`` / ``signal_workflow``); the worker then extracts it
    and roots the workflow / activity spans under it. But the ACP server dispatches
    from a bare async handler with no active span, so nothing is injected and the
    workflow's activities become DETACHED trace roots -- the business work shows up
    in Tempo as a fresh trace with no link back to the ``task/create`` /
    ``event/send`` that triggered it.

    Opening a span here gives the interceptor something to inject. It becomes a
    child of the ingress request span when one is active (front-of-request
    propagation), or a fresh per-turn root otherwise. Fail-open: never raises if
    OpenTelemetry isn't importable.
    """
    try:
        from opentelemetry import trace as _otel_trace
    except Exception:  # pragma: no cover - obs must never break a dispatch
        yield
        return
    tracer = _otel_trace.get_tracer("agentex.acp")
    # task_id goes on an attribute, NOT in the span name: a per-task span name is
    # high-cardinality and breaks span-name aggregation in Tempo.
    attributes = {"agentex.task_id": task_id} if task_id else None
    with tracer.start_as_current_span(name, kind=_otel_trace.SpanKind.PRODUCER, attributes=attributes):
        yield


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
        execution_timeout = timedelta(seconds=timeout_seconds) if timeout_seconds and timeout_seconds > 0 else None
        with _acp_dispatch_span("acp.task_create", task_id=task.id):
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
        with _acp_dispatch_span("acp.event_send", task_id=task.id):
            return await self._temporal_client.send_signal(
                workflow_id=task.id,
                signal=SignalName.RECEIVE_EVENT.value,
                payload=SendEventParams(
                    agent=agent,
                    task=task,
                    event=event,
                    request=request,
                ).model_dump(),
            )

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
