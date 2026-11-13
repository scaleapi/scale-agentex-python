"""SignalHandlerErrorInterceptor drops a signal whose handler raises unexpectedly, and re-raises the rest.

The inbound interceptor runs here against a fake ``next`` and a faked workflow context (the same patches as
``tests/lib/core/temporal/test_workflow_logging.py``), so no Temporal server is needed.
``test_signal_errors_replay.py`` checks the same rules inside Temporal's real workflow runtime.
"""

from __future__ import annotations

import sys
import asyncio
import inspect
import logging
from types import SimpleNamespace
from typing import Any, override

import pytest
import pydantic
from temporalio import workflow
from temporalio.worker import (
    HandleQueryInput,
    HandleSignalInput,
    HandleUpdateInput,
    ExecuteWorkflowInput,
    WorkflowInboundInterceptor,
    WorkflowInterceptorClassInput,
)
from temporalio.exceptions import (
    FailureError,
    TimeoutError as TemporalTimeoutError,
    ActivityError,
    TemporalError,
    CancelledError as TemporalCancelledError,
    ApplicationError,
    ChildWorkflowError,
)
from temporalio.worker.workflow_sandbox import RestrictedWorkflowAccessError

from agentex.lib.core.temporal.workers import signal_errors
from agentex.lib.core.temporal.workers.signal_errors import SignalHandlerErrorInterceptor

SIGNAL = "receive_event"


class _DeclaredError(Exception):
    """Stands in for a type listed in ``@workflow.defn(failure_exception_types=...)``."""


class _DeclaredTemporalError(TemporalError):
    """Stands in for a ``TemporalError`` declared a failure type, like the OpenAI Agents plugin's
    ``AgentsWorkflowError``."""


class _NondeterministicGroup(ExceptionGroup[Exception], workflow.NondeterminismError):
    """An exception group that is itself one of the SDK's own errors."""


class _ContinueAsNew(workflow.ContinueAsNewError):
    """What ``workflow.continue_as_new`` raises; ``ContinueAsNewError`` itself cannot be constructed."""


class _Evicted(BaseException):
    """Stands in for temporalio's private ``_WorkflowBeingEvictedError``."""


def _is_failure_exception(err: BaseException) -> bool:
    # What temporalio's workflow_is_failure_exception answers for a workflow declaring the two _Declared* types.
    return isinstance(err, (FailureError, asyncio.TimeoutError, _DeclaredError, _DeclaredTemporalError))


@pytest.fixture(autouse=True)
def workflow_context(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.DEBUG, logger=signal_errors.logger.name)

    def enter(*, replaying: bool) -> None:
        monkeypatch.setattr(workflow, "in_workflow", lambda: True)
        monkeypatch.setattr(
            workflow,
            "info",
            lambda: SimpleNamespace(workflow_id="task-123", run_id="run-456", workflow_type="ChatWorkflow"),
        )
        monkeypatch.setattr(workflow.unsafe, "is_replaying_history_events", lambda: replaying)
        monkeypatch.setattr(workflow, "is_failure_exception", _is_failure_exception)

    enter(replaying=False)
    return enter


class _Terminal(WorkflowInboundInterceptor):
    """End of the chain: records each call, then raises ``error`` or returns ``result``."""

    def __init__(self, *, error: BaseException | None = None, result: Any = None) -> None:
        # No super().__init__(): there is no next interceptor to delegate to.
        self.error = error
        self.result = result
        self.calls: list[Any] = []

    def _finish(self, input: Any) -> Any:
        self.calls.append(input)
        if self.error is not None:
            raise self.error
        return self.result

    @override
    async def handle_signal(self, input: HandleSignalInput) -> None:
        return self._finish(input)

    @override
    async def execute_workflow(self, input: ExecuteWorkflowInput) -> Any:
        return self._finish(input)

    @override
    async def handle_query(self, input: HandleQueryInput) -> Any:
        return self._finish(input)

    @override
    def handle_update_validator(self, input: HandleUpdateInput) -> None:
        self._finish(input)

    @override
    async def handle_update_handler(self, input: HandleUpdateInput) -> Any:
        return self._finish(input)


def _inbound(terminal: _Terminal) -> WorkflowInboundInterceptor:
    interceptor_class = SignalHandlerErrorInterceptor().workflow_interceptor_class(
        WorkflowInterceptorClassInput(unsafe_extern_functions={})
    )
    return interceptor_class(terminal)


def _signal(*args: Any) -> HandleSignalInput:
    return HandleSignalInput(signal=SIGNAL, args=list(args) or [{"content": None}], headers={})


def _dropped(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == signal_errors.logger.name]


def _validation_error() -> pydantic.ValidationError:
    # What a str-typed activity parameter raises when the event content is a dict rather than text.
    try:
        pydantic.TypeAdapter(str).validate_python({"type": "data"})
    except pydantic.ValidationError as err:
        return err
    raise AssertionError("expected a ValidationError")


def _activity_error() -> ActivityError:
    return ActivityError(
        "activity failed",
        scheduled_event_id=5,
        started_event_id=6,
        identity="worker",
        activity_type="call_llm",
        activity_id="1",
        retry_state=None,
    )


def _nested_group(depth: int, leaf: Exception) -> ExceptionGroup[Exception]:
    group = ExceptionGroup("level 0", [leaf])
    for level in range(1, depth):
        group = ExceptionGroup(f"level {level}", [group])
    return group


class _GroupThatCannotDerive(ExceptionGroup[Exception]):
    """A group subclass whose ``derive()`` fails, as one with extra constructor arguments can."""

    @override
    def derive(self, excs: Any) -> ExceptionGroup[Exception]:
        raise TypeError("cannot rebuild this group")


async def test_a_handled_signal_passes_through_untouched(caplog: pytest.LogCaptureFixture) -> None:
    result = object()
    terminal = _Terminal(result=result)
    signal = _signal({"content": "hello"})

    assert await _inbound(terminal).handle_signal(signal) is result

    assert len(terminal.calls) == 1 and terminal.calls[0] is signal
    assert not _dropped(caplog)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(AttributeError("'DataContent' object has no attribute 'content'"), id="AttributeError"),
        pytest.param(TypeError('can only concatenate str (not "dict") to str'), id="TypeError"),
        pytest.param(ValueError("expected text content"), id="ValueError"),
        pytest.param(KeyError("content"), id="KeyError"),
        pytest.param(_validation_error(), id="pydantic-ValidationError"),
        pytest.param(RuntimeError("any other handler bug"), id="RuntimeError"),
    ],
)
async def test_an_unexpected_handler_exception_is_logged_and_the_signal_dropped(
    caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    assert await _inbound(_Terminal(error=error)).handle_signal(_signal()) is None

    (record,) = _dropped(caplog)
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None and record.exc_info[1] is error
    assert record.__dict__["signal_name"] == SIGNAL
    assert record.__dict__["workflow_id"] == "task-123"
    assert record.__dict__["run_id"] == "run-456"
    message = record.getMessage()
    for expected in (repr(SIGNAL), "task-123", "run-456", "ChatWorkflow", type(error).__qualname__):
        assert expected in message


async def test_the_signal_arguments_are_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    sentinel = "user-content-4321"
    event = {"content": {"type": "data", "data": {"note": sentinel}}}

    await _inbound(_Terminal(error=AttributeError("'dict' object has no attribute 'strip'"))).handle_signal(
        _signal(event)
    )

    (record,) = _dropped(caplog)
    assert sentinel not in caplog.text
    assert all(sentinel not in repr(value) for value in record.__dict__.values())


@pytest.mark.parametrize(
    "error",
    [
        # Temporal fails the workflow for these, deliberately.
        pytest.param(ApplicationError("rejected the event", non_retryable=True), id="ApplicationError"),
        pytest.param(_activity_error(), id="ActivityError"),
        pytest.param(
            ChildWorkflowError(
                "child failed",
                namespace="default",
                workflow_id="child",
                run_id="child-run",
                workflow_type="Child",
                initiated_event_id=5,
                started_event_id=6,
                retry_state=None,
            ),
            id="ChildWorkflowError",
        ),
        pytest.param(TemporalCancelledError("cancelled"), id="temporalio-CancelledError"),
        pytest.param(
            TemporalTimeoutError("timed out", type=None, last_heartbeat_details=[]), id="temporalio-TimeoutError"
        ),
        pytest.param(asyncio.TimeoutError(), id="asyncio-TimeoutError"),
        pytest.param(_DeclaredError("declared in failure_exception_types"), id="declared-failure-exception-type"),
        pytest.param(_DeclaredTemporalError("agent run failed"), id="declared-TemporalError"),
        # The SDK's own errors: Temporal fails the task until the workflow code is fixed.
        pytest.param(workflow.NondeterminismError("nondeterministic"), id="NondeterminismError"),
        pytest.param(RestrictedWorkflowAccessError("datetime.datetime.now"), id="RestrictedWorkflowAccessError"),
        pytest.param(workflow.ReadOnlyContextError("mutated in a read-only context"), id="ReadOnlyContextError"),
        # Control flow, which is never caught at all.
        pytest.param(asyncio.CancelledError(), id="asyncio-CancelledError"),
        pytest.param(_ContinueAsNew(), id="continue-as-new"),
        pytest.param(_Evicted(), id="eviction"),
    ],
)
async def test_deliberate_outcomes_and_control_flow_propagate_unchanged(
    caplog: pytest.LogCaptureFixture, error: BaseException
) -> None:
    with pytest.raises(type(error)) as raised:
        await _inbound(_Terminal(error=error)).handle_signal(_signal())

    assert raised.value is error
    assert not _dropped(caplog)


async def test_a_replayed_drop_is_not_logged_again(workflow_context, caplog: pytest.LogCaptureFixture) -> None:
    workflow_context(replaying=True)

    assert await _inbound(_Terminal(error=AttributeError("no content"))).handle_signal(_signal()) is None

    assert not _dropped(caplog)


async def test_a_logging_failure_still_drops_the_signal_and_says_so_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("log pipeline is down")

    monkeypatch.setattr(signal_errors.logger, "error", broken)
    sentinel = "user-content-8642"

    assert (
        await _inbound(_Terminal(error=AttributeError("no content"))).handle_signal(_signal({"content": sentinel}))
        is None
    )

    err = capsys.readouterr().err
    for expected in (repr(SIGNAL), "task-123", "run-456", "AttributeError", "RuntimeError"):
        assert expected in err
    assert sentinel not in err


async def test_the_drop_is_logged_with_the_sandbox_lifted(caplog: pytest.LogCaptureFixture) -> None:
    # Handlers that import while emitting (rich's) would otherwise hit RestrictedWorkflowAccessError inside
    # temporalio's default sandbox and lose the record.
    seen: list[tuple[bool, bool]] = []

    class _Probe(logging.Handler):
        @override
        def emit(self, record: logging.LogRecord) -> None:
            seen.append((workflow.unsafe.is_sandbox_unrestricted(), workflow.unsafe.is_imports_passed_through()))

    probe = _Probe()
    signal_errors.logger.logger.addHandler(probe)
    try:
        await _inbound(_Terminal(error=AttributeError("no content"))).handle_signal(_signal())
    finally:
        signal_errors.logger.logger.removeHandler(probe)

    assert seen == [(True, True)]
    assert len(_dropped(caplog)) == 1
    assert not workflow.unsafe.is_sandbox_unrestricted() and not workflow.unsafe.is_imports_passed_through()


# temporalio checks an exception group as a whole and fails the task for any group that is not itself a failure
# exception, so a group re-raised for the failures inside it would wedge the workflow instead of failing it.
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ExceptionGroup("task group", [AttributeError("no content")]), id="plain-errors"),
        pytest.param(
            ExceptionGroup("outer", [ValueError("bad"), ExceptionGroup("inner", [KeyError("content")])]),
            id="nested-plain-errors",
        ),
        pytest.param(
            ExceptionGroup("unhandled errors in a TaskGroup", [ApplicationError("rejected", non_retryable=True)]),
            id="ApplicationError",
        ),
        pytest.param(ExceptionGroup("unhandled errors in a TaskGroup", [_activity_error()]), id="ActivityError"),
        pytest.param(ExceptionGroup("unhandled errors in a TaskGroup", [asyncio.TimeoutError()]), id="timeout"),
        pytest.param(
            ExceptionGroup("task group", [ValueError("bad"), ApplicationError("rejected", non_retryable=True)]),
            id="mixed",
        ),
        pytest.param(
            ExceptionGroup("outer", [ExceptionGroup("inner", [ApplicationError("rejected", non_retryable=True)])]),
            id="nested-ApplicationError",
        ),
        pytest.param(ExceptionGroup("task group", [_DeclaredError("declared")]), id="declared-failure-exception-type"),
        pytest.param(
            ExceptionGroup("unhandled errors in a TaskGroup", [_DeclaredTemporalError("agent run failed")]),
            id="declared-TemporalError",
        ),
    ],
)
async def test_an_exception_group_without_an_sdk_error_is_dropped(
    caplog: pytest.LogCaptureFixture, error: ExceptionGroup[Exception]
) -> None:
    assert await _inbound(_Terminal(error=error)).handle_signal(_signal()) is None

    (record,) = _dropped(caplog)
    assert record.exc_info is not None and record.exc_info[1] is error


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            ExceptionGroup("task group", [ValueError("bad"), workflow.NondeterminismError("nondeterministic")]),
            id="NondeterminismError",
        ),
        pytest.param(
            ExceptionGroup(
                "outer", [ExceptionGroup("inner", [RestrictedWorkflowAccessError("datetime.datetime.now")])]
            ),
            id="nested-RestrictedWorkflowAccessError",
        ),
        pytest.param(
            ExceptionGroup(
                "task group",
                [ApplicationError("rejected", non_retryable=True), workflow.ReadOnlyContextError("mutated")],
            ),
            id="ReadOnlyContextError-beside-ApplicationError",
        ),
        pytest.param(
            _GroupThatCannotDerive("task group", [ValueError("bad"), workflow.NondeterminismError("nondeterministic")]),
            id="group-that-cannot-derive",
        ),
        pytest.param(
            ExceptionGroup("outer", [_NondeterministicGroup("inner", [ValueError("bad")])]),
            id="nested-group-that-is-an-sdk-error",
        ),
    ],
)
async def test_an_exception_group_holding_an_sdk_error_propagates_unchanged(
    caplog: pytest.LogCaptureFixture, error: ExceptionGroup[Exception]
) -> None:
    with pytest.raises(ExceptionGroup) as raised:
        await _inbound(_Terminal(error=error)).handle_signal(_signal())

    assert raised.value is error
    assert not _dropped(caplog)


async def test_an_exception_group_that_is_itself_a_failure_exception_propagates(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # What a workflow declaring failure_exception_types=[Exception] gets: Temporal fails the workflow.
    monkeypatch.setattr(workflow, "is_failure_exception", lambda err: isinstance(err, Exception))
    error = ExceptionGroup("task group", [AttributeError("no content")])

    with pytest.raises(ExceptionGroup) as raised:
        await _inbound(_Terminal(error=error)).handle_signal(_signal())

    assert raised.value is error
    assert not _dropped(caplog)


def test_a_group_nested_past_the_recursion_limit_is_classified_without_recursing() -> None:
    depth = sys.getrecursionlimit() + 100

    assert not signal_errors._left_to_temporal(_nested_group(depth, AttributeError("no content")))
    assert signal_errors._left_to_temporal(_nested_group(depth, workflow.NondeterminismError("nondeterministic")))


@pytest.mark.parametrize(
    "method", ["execute_workflow", "handle_query", "handle_update_validator", "handle_update_handler"]
)
async def test_only_signal_handling_is_changed(caplog: pytest.LogCaptureFixture, method: str) -> None:
    error = AttributeError("not a signal")
    inbound = _inbound(_Terminal(error=error))

    with pytest.raises(AttributeError) as raised:
        outcome = getattr(inbound, method)(object())
        if inspect.isawaitable(outcome):
            await outcome

    assert raised.value is error
    assert not _dropped(caplog)
