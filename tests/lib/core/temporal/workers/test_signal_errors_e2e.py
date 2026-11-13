"""End to end on a local Temporal dev server: a poison signal no longer wedges its workflow.

Needs the Temporal CLI (``temporal``) on PATH and is skipped without it; CI has none, and this never
downloads a server. ``test_signal_errors_replay.py`` covers the same behaviour hermetically.
"""

from __future__ import annotations

import gc
import uuid
import shutil
import asyncio
import logging
from typing import Any
from datetime import timedelta
from collections.abc import AsyncIterator

import pytest
from temporalio import workflow
from temporalio.client import Client, WorkflowHandle, WorkflowFailureError, WorkflowExecutionStatus
from temporalio.worker import Worker, UnsandboxedWorkflowRunner
from temporalio.testing import WorkflowEnvironment
from temporalio.exceptions import TemporalError, ApplicationError
from temporalio.api.enums.v1 import EventType

from agentex.lib.core.temporal.workers import signal_errors
from agentex.lib.core.temporal.workers.signal_errors import SignalHandlerErrorInterceptor

TEMPORAL_CLI = shutil.which("temporal")

pytestmark = pytest.mark.skipif(TEMPORAL_CLI is None, reason="needs the Temporal CLI (`temporal`) on PATH")

SENTINEL = "user-content-8642"
POISON = {"content": {"type": "data", "data": {"note": SENTINEL}}}
VALID = {"content": " hello "}
TASK_FAILED = EventType.EVENT_TYPE_WORKFLOW_TASK_FAILED


@workflow.defn
class EventWorkflow:
    """Completes with the first event's text. Like the tutorials' handlers, it assumes text content."""

    def __init__(self) -> None:
        self._texts: list[str] = []

    @workflow.run
    async def run(self) -> list[str]:
        await workflow.wait_condition(lambda: bool(self._texts))
        return self._texts

    @workflow.signal
    def receive_event(self, event: dict[str, Any]) -> None:
        self._texts.append(event["content"].strip())

    @workflow.query
    def texts(self) -> list[str]:
        return list(self._texts)


class DeclaredTemporalError(TemporalError):
    """Like the OpenAI Agents plugin's AgentsWorkflowError: a TemporalError declared a failure type."""


class _TaskGroupChecks:
    """Checks each event in an ``asyncio.TaskGroup`` whose child rejects non-text content on purpose."""

    rejection: type[Exception]

    def __init__(self) -> None:
        self._texts: list[str] = []

    @workflow.signal
    async def receive_event(self, event: dict[str, Any]) -> None:
        async with asyncio.TaskGroup() as group:
            group.create_task(self._require_text(event))
        self._texts.append(event["content"].strip())

    async def _require_text(self, event: dict[str, Any]) -> None:
        if not isinstance(event["content"], str):
            raise self.rejection("event content is not text")

    async def _first_texts(self) -> list[str]:
        await workflow.wait_condition(lambda: bool(self._texts))
        return self._texts


@workflow.defn
class TaskGroupWorkflow(_TaskGroupChecks):
    rejection = ApplicationError

    @workflow.run
    async def run(self) -> list[str]:
        return await self._first_texts()


@workflow.defn(failure_exception_types=[DeclaredTemporalError])
class DeclaredErrorTaskGroupWorkflow(_TaskGroupChecks):
    rejection = DeclaredTemporalError

    @workflow.run
    async def run(self) -> list[str]:
        return await self._first_texts()


class DeclaredError(Exception):
    pass


@workflow.defn(failure_exception_types=[DeclaredError])
class DeclaredFailureWorkflow:
    @workflow.run
    async def run(self) -> None:
        await workflow.wait_condition(lambda: False)

    @workflow.signal
    def receive_event(self, event: dict[str, Any]) -> None:
        raise DeclaredError("declared to fail the workflow")


@pytest.fixture(scope="module")
async def client() -> AsyncIterator[Client]:
    assert TEMPORAL_CLI is not None
    env = await WorkflowEnvironment.start_local(
        dev_server_existing_path=TEMPORAL_CLI, dev_server_startup_timeout=timedelta(seconds=30)
    )
    try:
        yield env.client
    finally:
        await env.shutdown()


def _worker(client: Client, workflow_class: type, *, with_interceptor: bool) -> Worker:
    return Worker(
        client,
        task_queue=f"signal-errors-e2e-{uuid.uuid4()}",
        workflows=[workflow_class],
        workflow_runner=UnsandboxedWorkflowRunner(),
        interceptors=[SignalHandlerErrorInterceptor()] if with_interceptor else [],
    )


async def _event_types(handle: WorkflowHandle[Any, Any]) -> list[int]:
    return [event.event_type async for event in handle.fetch_history_events()]


async def _wait_for_event(handle: WorkflowHandle[Any, Any], event_type: int) -> None:
    async def poll() -> None:
        while event_type not in await _event_types(handle):
            await asyncio.sleep(0.1)

    await asyncio.wait_for(poll(), timeout=10)


async def test_a_poison_signal_is_dropped_and_the_next_signal_is_processed(
    client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger=signal_errors.logger.name)
    async with _worker(client, EventWorkflow, with_interceptor=True) as worker:
        handle = await client.start_workflow(
            EventWorkflow.run, id=f"signal-errors-e2e-{uuid.uuid4()}", task_queue=worker.task_queue
        )
        await handle.signal(EventWorkflow.receive_event, POISON)
        await handle.signal(EventWorkflow.receive_event, VALID)

        assert await asyncio.wait_for(handle.result(), timeout=10) == ["hello"]
        assert await handle.query(EventWorkflow.texts) == ["hello"]

    assert TASK_FAILED not in await _event_types(handle)
    (record,) = [record for record in caplog.records if record.name == signal_errors.logger.name]
    assert record.__dict__["workflow_id"] == handle.id
    assert record.exc_info is not None and isinstance(record.exc_info[1], AttributeError)
    assert SENTINEL not in caplog.text


@pytest.mark.parametrize("workflow_class", [TaskGroupWorkflow, DeclaredErrorTaskGroupWorkflow])
async def test_a_task_group_rejecting_the_signal_is_dropped_rather_than_wedging_the_workflow(
    client: Client,
    caplog: pytest.LogCaptureFixture,
    workflow_class: type[TaskGroupWorkflow | DeclaredErrorTaskGroupWorkflow],
) -> None:
    # Temporal fails the task, not the workflow, for an exception group, even one holding only a failure
    # exception: an ApplicationError, or a TemporalError the workflow declares a failure type.
    caplog.set_level(logging.DEBUG, logger=signal_errors.logger.name)
    async with _worker(client, workflow_class, with_interceptor=True) as worker:
        handle = await client.start_workflow(
            workflow_class.run, id=f"signal-errors-e2e-{uuid.uuid4()}", task_queue=worker.task_queue
        )
        await handle.signal("receive_event", POISON)
        await handle.signal("receive_event", VALID)

        assert await asyncio.wait_for(handle.result(), timeout=10) == ["hello"]

    assert TASK_FAILED not in await _event_types(handle)
    (record,) = [record for record in caplog.records if record.name == signal_errors.logger.name]
    assert record.exc_info is not None and isinstance(record.exc_info[1], ExceptionGroup)
    assert type(record.exc_info[1].exceptions[0]) is workflow_class.rejection


# Each retry of the failing task hands the valid signal to an activation that aborts before running it; newer
# temporalio versions also leave the workflow's run coroutine unstarted.
@pytest.mark.filterwarnings("ignore:coroutine .*(run_signal|run_workflow).* was never awaited:RuntimeWarning")
async def test_without_the_interceptor_the_poison_signal_wedges_the_workflow(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The failed activations' log records hold tracebacks that would keep those coroutines alive in pytest's log
    # capture until after the test, where the filter above no longer applies.
    monkeypatch.setattr(logging.getLogger("temporalio.worker._workflow_instance"), "disabled", True)
    async with _worker(client, EventWorkflow, with_interceptor=False) as worker:
        handle = await client.start_workflow(
            EventWorkflow.run, id=f"signal-errors-e2e-{uuid.uuid4()}", task_queue=worker.task_queue
        )
        await handle.signal(EventWorkflow.receive_event, POISON)
        await _wait_for_event(handle, TASK_FAILED)
        await handle.signal(EventWorkflow.receive_event, VALID)

        with pytest.raises(TimeoutError):
            await asyncio.wait_for(handle.result(), timeout=3)
        assert (await handle.describe()).status == WorkflowExecutionStatus.RUNNING
        await handle.terminate("test cleanup")
    gc.collect()


async def test_a_declared_failure_exception_type_still_fails_the_workflow(client: Client) -> None:
    async with _worker(client, DeclaredFailureWorkflow, with_interceptor=True) as worker:
        handle = await client.start_workflow(
            DeclaredFailureWorkflow.run, id=f"signal-errors-e2e-{uuid.uuid4()}", task_queue=worker.task_queue
        )
        await handle.signal(DeclaredFailureWorkflow.receive_event, POISON)

        with pytest.raises(WorkflowFailureError) as raised:
            await asyncio.wait_for(handle.result(), timeout=10)

    assert isinstance(raised.value.cause, ApplicationError)
    assert raised.value.cause.type == "DeclaredError"
    assert TASK_FAILED not in await _event_types(handle)
