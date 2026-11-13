"""AgentexWorker installs SignalHandlerErrorInterceptor by default, ahead of the caller's interceptors.

As in test_worker_tracing.py, the Client and Worker configuration stay real and only their network boundary
is replaced; the tests read the workflow inbound interceptor chain the Worker builds for every workflow.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any, override
from unittest.mock import Mock, AsyncMock
from collections.abc import Callable, Awaitable

import pytest
from temporalio import workflow
from temporalio.worker import (
    Worker,
    Interceptor,
    HandleSignalInput,
    WorkflowInboundInterceptor,
    WorkflowInterceptorClassInput,
)
from temporalio.exceptions import FailureError
from temporalio.bridge.client import Client as BridgeClient
from temporalio.bridge.worker import Worker as BridgeWorker
from temporalio.contrib.opentelemetry import TracingWorkflowInboundInterceptor

from agentex.lib.core.temporal.workers.worker import AgentexWorker
from agentex.lib.core.temporal.workers.signal_errors import SignalHandlerErrorInterceptor

TRACE_ENV = "AGENTEX_TEMPORAL_TRACE_INTERCEPTOR_ENABLED"
DROP_SIGNAL_ERRORS = SignalHandlerErrorInterceptor().workflow_interceptor_class(
    WorkflowInterceptorClassInput(unsafe_extern_functions={})
)

Chain = list[type[WorkflowInboundInterceptor]]


@workflow.defn
class _Workflow:
    @workflow.run
    async def run(self) -> None:
        pass


class _CallerInterceptor(Interceptor):
    """A caller's interceptor that records the outcome of each signal it wraps."""

    def __init__(self, name: str, seen: list[tuple[str, BaseException | None]]) -> None:
        self.name = name

        class Inbound(WorkflowInboundInterceptor):
            @override
            async def handle_signal(self, input: HandleSignalInput) -> None:
                try:
                    await self.next.handle_signal(input)
                except Exception as err:
                    seen.append((name, err))
                    raise
                seen.append((name, None))

        self.inbound = Inbound

    @override
    def workflow_interceptor_class(self, input: WorkflowInterceptorClassInput) -> type[WorkflowInboundInterceptor]:
        return self.inbound


def _names(chain: Chain, *callers: _CallerInterceptor) -> list[str]:
    by_class: dict[type[WorkflowInboundInterceptor], str] = {caller.inbound: caller.name for caller in callers}
    by_class[DROP_SIGNAL_ERRORS] = "drop-signal-errors"
    by_class[TracingWorkflowInboundInterceptor] = "tracing"
    return [by_class.get(interceptor_class, interceptor_class.__qualname__) for interceptor_class in chain]


@pytest.fixture
def build_chain(monkeypatch: pytest.MonkeyPatch) -> Callable[[AgentexWorker], Awaitable[Chain]]:
    monkeypatch.delenv("DD_AGENT_HOST", raising=False)
    # Keep Client and Worker configuration real; replace their network boundary.
    monkeypatch.setattr(BridgeClient, "connect", AsyncMock(return_value=Mock()))
    monkeypatch.setattr(BridgeWorker, "create", Mock(return_value=Mock()))
    built: list[Worker] = []

    async def capture(worker: Worker) -> None:
        built.append(worker)

    monkeypatch.setattr(Worker, "run", capture)

    async def run(agentex_worker: AgentexWorker) -> Chain:
        monkeypatch.setattr(agentex_worker, "start_health_check_server", AsyncMock())
        monkeypatch.setattr(agentex_worker, "_register_agent", AsyncMock())
        await agentex_worker.run(activities=[], workflows=[_Workflow])
        worker = built.pop()
        assert worker._workflow_worker is not None
        return list(worker._workflow_worker._interceptor_classes)

    return run


@pytest.mark.parametrize("tracing_enabled", [True, False])
async def test_installed_by_default_ahead_of_the_callers_interceptors(
    monkeypatch: pytest.MonkeyPatch, build_chain, tracing_enabled: bool
) -> None:
    monkeypatch.setenv(TRACE_ENV, str(tracing_enabled).lower())
    seen: list[tuple[str, BaseException | None]] = []
    first, second = _CallerInterceptor("first", seen), _CallerInterceptor("second", seen)
    callers = [first, second]
    agentex_worker = AgentexWorker(task_queue="test-signal-errors", health_check_port=8080, interceptors=callers)

    chain = await build_chain(agentex_worker)

    # Temporal prepends the client's interceptors (tracing); the worker's own follow in the order given.
    assert _names(chain, first, second) == [
        *(["tracing"] if tracing_enabled else []),
        "drop-signal-errors",
        "first",
        "second",
    ]
    assert callers == [first, second]
    assert agentex_worker.interceptors is callers


async def test_opting_out_passes_the_callers_interceptors_unchanged(
    monkeypatch: pytest.MonkeyPatch, build_chain
) -> None:
    monkeypatch.setenv(TRACE_ENV, "false")
    seen: list[tuple[str, BaseException | None]] = []
    first, second = _CallerInterceptor("first", seen), _CallerInterceptor("second", seen)
    agentex_worker = AgentexWorker(
        task_queue="test-signal-errors",
        health_check_port=8080,
        interceptors=[first, second],
        drop_signals_on_handler_error=False,
    )

    assert _names(await build_chain(agentex_worker), first, second) == ["first", "second"]


async def test_a_caller_placed_interceptor_is_not_added_twice(monkeypatch: pytest.MonkeyPatch, build_chain) -> None:
    monkeypatch.setenv(TRACE_ENV, "false")
    first = _CallerInterceptor("first", [])
    agentex_worker = AgentexWorker(
        task_queue="test-signal-errors", health_check_port=8080, interceptors=[first, SignalHandlerErrorInterceptor()]
    )

    assert _names(await build_chain(agentex_worker), first) == ["first", "drop-signal-errors"]


async def test_the_default_interceptors_list_is_not_mutated(monkeypatch: pytest.MonkeyPatch, build_chain) -> None:
    monkeypatch.setenv(TRACE_ENV, "false")
    default = inspect.signature(AgentexWorker.__init__).parameters["interceptors"].default

    for _ in range(2):
        chain = await build_chain(AgentexWorker(task_queue="test-signal-errors", health_check_port=8080))
        assert _names(chain) == ["drop-signal-errors"]

    assert default == []


async def test_the_callers_interceptors_see_the_exception_before_the_signal_is_dropped(
    monkeypatch: pytest.MonkeyPatch, build_chain
) -> None:
    monkeypatch.setenv(TRACE_ENV, "false")
    seen: list[tuple[str, BaseException | None]] = []
    first, second = _CallerInterceptor("first", seen), _CallerInterceptor("second", seen)
    chain = await build_chain(
        AgentexWorker(task_queue="test-signal-errors", health_check_port=8080, interceptors=[first, second])
    )
    monkeypatch.setattr(workflow, "in_workflow", lambda: True)
    monkeypatch.setattr(
        workflow, "info", lambda: SimpleNamespace(workflow_id="task-1", run_id="run-1", workflow_type="W")
    )
    monkeypatch.setattr(workflow.unsafe, "is_replaying_history_events", lambda: False)
    monkeypatch.setattr(workflow, "is_failure_exception", lambda err: isinstance(err, FailureError))
    error = AttributeError("'DataContent' object has no attribute 'content'")

    class Handler(WorkflowInboundInterceptor):
        def __init__(self) -> None:
            pass

        @override
        async def handle_signal(self, input: HandleSignalInput) -> None:
            raise error

    # Assemble the chain the way the workflow instance does: the first class listed is the outermost.
    inbound: WorkflowInboundInterceptor = Handler()
    for interceptor_class in reversed(chain):
        inbound = interceptor_class(inbound)
    outcome: Any = await inbound.handle_signal(HandleSignalInput(signal="receive_event", args=[{}], headers={}))

    assert outcome is None
    assert seen == [("second", error), ("first", error)]
