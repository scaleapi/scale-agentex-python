"""SignalHandlerErrorInterceptor in Temporal's real workflow runtime, replayed from hand-built histories.

``Replayer`` drives the real worker machinery (Core and the Python workflow instance) in-process, so no
Temporal server is needed. Each history records what a worker with the interceptor does, and replay fails
whenever the replaying worker would act differently, e.g. fail a workflow task the history completed.
"""

from __future__ import annotations

import gc
import json
import base64
import asyncio
import logging
from typing import Any
from concurrent.futures import ThreadPoolExecutor

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner
from temporalio.exceptions import TemporalError, ApplicationError

from agentex.lib.core.temporal.workers import signal_errors
from agentex.lib.core.temporal.workers.signal_errors import SignalHandlerErrorInterceptor

TASK_QUEUE = "signal-errors-replay"
EVENT_TIME = "2026-11-12T00:00:00Z"

POISON = {"content": {"type": "data", "data": {"note": "not text"}}}
VALID = {"content": " hello "}


class DeclaredError(Exception):
    """Listed in the workflow's ``failure_exception_types``, so it is meant to fail the workflow."""


@workflow.defn(name="SignalErrorsReplayWorkflow", failure_exception_types=[DeclaredError])
class SignalErrorsReplayWorkflow:
    def __init__(self) -> None:
        self._texts: list[str] = []

    @workflow.run
    async def run(self) -> list[str]:
        await workflow.wait_condition(lambda: bool(self._texts))
        return self._texts

    @workflow.signal(name="receive_event")
    def receive_event(self, event: dict[str, Any]) -> None:
        raise_as = event.get("raise")
        if raise_as == "application":
            raise ApplicationError("rejected on purpose", non_retryable=True)
        if raise_as == "declared":
            raise DeclaredError("declared to fail the workflow")
        if raise_as == "nondeterminism":
            raise workflow.NondeterminismError("broke determinism")
        # Like the tutorials' receive_event handlers this assumes text, so POISON raises AttributeError.
        self._texts.append(event["content"].strip())


def _payload(value: Any) -> dict[str, Any]:
    return {
        "metadata": {"encoding": base64.b64encode(b"json/plain").decode()},
        "data": base64.b64encode(json.dumps(value).encode()).decode(),
    }


def _history(*signal_tasks: list[dict[str, Any]], closed_by: str) -> WorkflowHistory:
    """A run that starts, handles each list of signals in one workflow task, then completes or fails."""
    events: list[dict[str, Any]] = [
        {
            "eventType": "EVENT_TYPE_WORKFLOW_EXECUTION_STARTED",
            "eventTime": EVENT_TIME,
            "workflowExecutionStartedEventAttributes": {
                "workflowType": {"name": "SignalErrorsReplayWorkflow"},
                "taskQueue": {"name": TASK_QUEUE},
                "workflowTaskTimeout": "10s",
                "originalExecutionRunId": "5d1f3c2e-8a4b-4c6d-9e0f-1a2b3c4d5e6f",
            },
        }
    ]

    def workflow_task() -> int:
        scheduled = len(events) + 1
        events.extend(
            [
                {
                    "eventType": "EVENT_TYPE_WORKFLOW_TASK_SCHEDULED",
                    "workflowTaskScheduledEventAttributes": {
                        "taskQueue": {"name": TASK_QUEUE},
                        "startToCloseTimeout": "10s",
                        "attempt": 1,
                    },
                },
                {
                    "eventType": "EVENT_TYPE_WORKFLOW_TASK_STARTED",
                    "eventTime": EVENT_TIME,
                    "workflowTaskStartedEventAttributes": {"scheduledEventId": str(scheduled)},
                },
                {
                    "eventType": "EVENT_TYPE_WORKFLOW_TASK_COMPLETED",
                    "workflowTaskCompletedEventAttributes": {
                        "scheduledEventId": str(scheduled),
                        "startedEventId": str(scheduled + 1),
                    },
                },
            ]
        )
        return scheduled + 2

    completed_task = workflow_task()
    for signals in signal_tasks:
        events.extend(
            {
                "eventType": "EVENT_TYPE_WORKFLOW_EXECUTION_SIGNALED",
                "workflowExecutionSignaledEventAttributes": {
                    "signalName": "receive_event",
                    "input": {"payloads": [_payload(signal)]},
                },
            }
            for signal in signals
        )
        completed_task = workflow_task()

    if closed_by == "completed":
        events.append(
            {
                "eventType": "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED",
                "workflowExecutionCompletedEventAttributes": {
                    "result": {"payloads": [_payload(["hello"])]},
                    "workflowTaskCompletedEventId": str(completed_task),
                },
            }
        )
    else:
        events.append(
            {
                "eventType": "EVENT_TYPE_WORKFLOW_EXECUTION_FAILED",
                "workflowExecutionFailedEventAttributes": {
                    "failure": {"message": "failed on purpose"},
                    "workflowTaskCompletedEventId": str(completed_task),
                },
            }
        )
    for event_id, event in enumerate(events, start=1):
        event["eventId"] = str(event_id)
    return WorkflowHistory.from_json("signal-errors-replay", {"events": events})


async def _replay(history: WorkflowHistory, *, with_interceptor: bool) -> Exception | None:
    with ThreadPoolExecutor(max_workers=1) as executor:
        replayer = Replayer(
            workflows=[SignalErrorsReplayWorkflow],
            workflow_runner=UnsandboxedWorkflowRunner(),
            interceptors=[SignalHandlerErrorInterceptor()] if with_interceptor else [],
            workflow_task_executor=executor,
        )
        result = await replayer.replay_workflow(history, raise_on_replay_failure=False)
    return result.replay_failure


POISON_THEN_VALID = [
    pytest.param(([POISON], [VALID]), id="separate-workflow-tasks"),
    pytest.param(([POISON, VALID],), id="same-workflow-task"),
]


@pytest.mark.parametrize("signal_tasks", POISON_THEN_VALID)
async def test_a_poison_signal_is_dropped_and_the_next_signal_completes_the_workflow(
    signal_tasks: tuple[list[dict[str, Any]], ...], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger=signal_errors.logger.name)

    failure = await _replay(_history(*signal_tasks, closed_by="completed"), with_interceptor=True)

    assert failure is None
    # Every replay re-runs the handler; the drop is logged when it happens, not again on each replay.
    assert not [record for record in caplog.records if record.name == signal_errors.logger.name]


@pytest.mark.filterwarnings("ignore:coroutine .*run_signal.* was never awaited:RuntimeWarning")
@pytest.mark.parametrize("signal_tasks", POISON_THEN_VALID)
async def test_without_the_interceptor_the_poison_signal_fails_its_workflow_task(
    signal_tasks: tuple[list[dict[str, Any]], ...],
) -> None:
    failure = await _replay(_history(*signal_tasks, closed_by="completed"), with_interceptor=False)

    assert failure is not None
    assert "'dict' object has no attribute 'strip'" in str(failure)
    # When both signals share the task, the failed activation never runs the valid signal's handler at all and
    # Python finalizes its coroutine unawaited. Collect it now, under the filter above, not in a later test.
    gc.collect()


@pytest.mark.parametrize("raise_as", ["application", "declared"])
async def test_a_deliberate_workflow_failure_still_fails_the_workflow(raise_as: str) -> None:
    # The history closes with WorkflowExecutionFailed right after the signal's task: dropping the
    # exception instead would leave the workflow running, which replay reports as nondeterminism.
    history = _history([{"raise": raise_as}], closed_by="failed")

    assert await _replay(history, with_interceptor=True) is None


async def test_a_nondeterminism_error_still_fails_the_workflow_task() -> None:
    # Were it dropped, the next signal would complete the workflow exactly as this history says.
    history = _history([{"raise": "nondeterminism"}], [VALID], closed_by="completed")

    failure = await _replay(history, with_interceptor=True)

    assert failure is not None
    assert "broke determinism" in str(failure)


class WorkerDeclaredError(TemporalError):
    """Declared at worker level, as the OpenAI Agents plugin declares its ``AgentsWorkflowError``."""


class DeclaredGroup(ExceptionGroup[Exception]):
    """An exception group class the workflow declares a failure type."""


class NondeterministicGroup(ExceptionGroup[Exception], workflow.NondeterminismError):
    """An exception group class that is itself one of the SDK's own errors."""


async def _raise(err: Exception) -> None:
    raise err


@workflow.defn(name="SignalErrorsReplayWorkflow", failure_exception_types=[DeclaredGroup])
class GroupReplayWorkflow:
    """Raises exception groups from an async signal handler, as an ``asyncio.TaskGroup`` does."""

    def __init__(self) -> None:
        self._texts: list[str] = []

    @workflow.run
    async def run(self) -> list[str]:
        await workflow.wait_condition(lambda: bool(self._texts))
        return self._texts

    @workflow.signal(name="receive_event")
    async def receive_event(self, event: dict[str, Any]) -> None:
        shape = event.get("raise")
        if shape == "task-group-application":
            async with asyncio.TaskGroup() as group:
                group.create_task(_raise(ApplicationError("rejected on purpose", non_retryable=True)))
        elif shape == "task-group-worker-declared":
            async with asyncio.TaskGroup() as group:
                group.create_task(_raise(WorkerDeclaredError("agent run failed")))
        elif shape == "task-group-nondeterminism":
            async with asyncio.TaskGroup() as group:
                group.create_task(_raise(workflow.NondeterminismError("broke determinism")))
        elif shape == "worker-declared":
            raise WorkerDeclaredError("agent run failed")
        elif shape == "nested-declared-group":
            raise ExceptionGroup("outer", [DeclaredGroup("inner", [ValueError("bad")])])
        elif shape == "declared-group-holding-nondeterminism":
            raise DeclaredGroup("group", [workflow.NondeterminismError("broke determinism")])
        elif shape == "application-in-nondeterministic-group":
            raise ExceptionGroup("outer", [NondeterministicGroup("inner", [ApplicationError("rejected")])])
        else:
            self._texts.append(event["content"].strip())


async def _replay_groups(history: WorkflowHistory, *, with_interceptor: bool) -> Exception | None:
    with ThreadPoolExecutor(max_workers=1) as executor:
        replayer = Replayer(
            workflows=[GroupReplayWorkflow],
            workflow_runner=UnsandboxedWorkflowRunner(),
            interceptors=[SignalHandlerErrorInterceptor()] if with_interceptor else [],
            workflow_task_executor=executor,
            workflow_failure_exception_types=[WorkerDeclaredError],
        )
        result = await replayer.replay_workflow(history, raise_on_replay_failure=False)
    # A failed activation leaves coroutines it never started; finalize them here, under the tests' warning filter.
    gc.collect()
    return result.replay_failure


UNSTARTED_COROUTINES = "ignore:coroutine .*(run_signal|run_workflow).* was never awaited:RuntimeWarning"


# Temporal checks only the outermost exception, so it fails the task for any group that is not itself a failure
# exception, whatever the group holds.
@pytest.mark.filterwarnings(UNSTARTED_COROUTINES)
@pytest.mark.parametrize("shape", ["task-group-application", "task-group-worker-declared", "nested-declared-group"])
async def test_an_exception_group_of_failures_is_dropped_rather_than_wedging_the_workflow(shape: str) -> None:
    history = _history([{"raise": shape}], [VALID], closed_by="completed")

    assert await _replay_groups(history, with_interceptor=True) is None
    assert await _replay_groups(history, with_interceptor=False) is not None


@pytest.mark.parametrize("shape", ["worker-declared", "declared-group-holding-nondeterminism"])
async def test_a_declared_failure_type_raised_from_the_handler_still_fails_the_workflow(shape: str) -> None:
    history = _history([{"raise": shape}], closed_by="failed")

    assert await _replay_groups(history, with_interceptor=True) is None


@pytest.mark.filterwarnings(UNSTARTED_COROUTINES)
@pytest.mark.parametrize("shape", ["task-group-nondeterminism", "application-in-nondeterministic-group"])
async def test_an_exception_group_holding_an_sdk_error_still_fails_the_workflow_task(shape: str) -> None:
    history = _history([{"raise": shape}], [VALID], closed_by="completed")

    assert await _replay_groups(history, with_interceptor=True) is not None
