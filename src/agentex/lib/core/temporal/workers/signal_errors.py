"""Stop one bad signal from wedging a Temporal workflow.

When a signal handler raises an exception that Temporal does not treat as a workflow failure, the
*workflow task* fails. The server retries that task forever, every retry replays the same signal from
history and raises again, so the workflow never progresses and every later signal is ignored.
:class:`SignalHandlerErrorInterceptor` logs and drops such a signal instead, as Temporal already does for a
signal whose arguments fail to deserialize, and the workflow carries on.
"""

from __future__ import annotations

import sys
import contextlib
from typing import override

from temporalio import workflow
from temporalio.worker import (
    Interceptor,
    HandleSignalInput,
    WorkflowInboundInterceptor,
    WorkflowInterceptorClassInput,
)
from temporalio.exceptions import TemporalError

from agentex.lib.core.temporal.logging import make_workflow_logger

__all__ = ["SignalHandlerErrorInterceptor"]

logger = make_workflow_logger(__name__)


class SignalHandlerErrorInterceptor(Interceptor):
    """Worker interceptor that logs and drops a signal whose handler raises an unexpected exception.

    Without it, one malformed event (``content`` that is ``None``, a ``DataContent``, a
    ``ToolResponseContent`` holding a dict, ...) sent to a handler that assumes text wedges the task's
    workflow forever. With it, the exception is logged replay-safely with the signal name and the workflow
    and run IDs, and the handler returns normally. The signal's arguments are not logged, but the
    exception's message and traceback are, and they can quote parts of them (a pydantic ``ValidationError``
    shows the rejected input).

    Everything Temporal gives a deliberate meaning to is re-raised unchanged: exceptions that
    ``workflow.is_failure_exception`` accepts still fail the workflow (any ``FailureError`` such as
    ``ApplicationError``, ``asyncio.TimeoutError``, and types declared with
    ``@workflow.defn(failure_exception_types=...)`` or the worker's ``workflow_failure_exception_types``);
    the SDK's own errors that are not declared failures (``NondeterminismError``, the sandbox's
    ``RestrictedWorkflowAccessError``, ``ReadOnlyContextError``, ...) still fail the task, also inside an
    ``ExceptionGroup`` that is not itself a failure exception; and ``BaseException``s such as
    ``asyncio.CancelledError`` and continue-as-new are never caught. Any other exception group, such as one from an ``asyncio.TaskGroup``
    whose child raised an ``ApplicationError``, is dropped: Temporal does not look inside groups, so
    re-raising it would fail the task on every retry rather than fail the workflow.

    Two consequences to keep in mind:

    - Dropping is not a rollback. Whatever the handler did before it raised is kept: state it changed,
      and activities, timers or child workflows it started. Validate a signal's input before acting on it.
    - Once a signal has been dropped, the workflow's history depends on the drop. A worker that replays
      that history without this interceptor (``drop_signals_on_handler_error=False``, an SDK version from
      before it, or a ``temporalio.worker.Replayer`` built without it) raises in the handler again and
      fails the workflow task, wedging the workflow until a worker with the interceptor picks it up. Pass
      ``interceptors=[SignalHandlerErrorInterceptor()]`` to replay tests, and avoid turning it off or rolling
      back past it while such workflows are open.

    ``AgentexWorker`` installs it by default (``drop_signals_on_handler_error=False`` opts out). A worker
    built directly with ``temporalio.worker.Worker`` should list it before its own interceptors, so they
    still see the exception::

        Worker(client, ..., interceptors=[SignalHandlerErrorInterceptor(), *my_interceptors])
    """

    @override
    def workflow_interceptor_class(self, input: WorkflowInterceptorClassInput) -> type[WorkflowInboundInterceptor]:
        return _SignalHandlerErrorInboundInterceptor


class _SignalHandlerErrorInboundInterceptor(WorkflowInboundInterceptor):
    @override
    async def handle_signal(self, input: HandleSignalInput) -> None:
        try:
            return await self.next.handle_signal(input)
        except Exception as err:  # not BaseException: cancellation, continue-as-new and eviction pass through
            if _left_to_temporal(err):
                raise
            _log_dropped_signal(input.signal, err)


def _left_to_temporal(err: Exception) -> bool:
    """Whether ``err`` must reach Temporal as raised rather than be dropped with its signal.

    Mirrors temporalio's ``_WorkflowInstanceImpl._run_top_level_workflow_function``, which fails the
    workflow for an exception ``workflow.is_failure_exception`` accepts (a ``FailureError``,
    ``asyncio.TimeoutError``, or a type declared on the workflow definition, a dynamic workflow's config or
    the worker) and fails the task for any other ``Exception``. Of the latter, the SDK's own errors
    (``NondeterminismError`` and the sandbox's ``RestrictedWorkflowAccessError``, ``ReadOnlyContextError``,
    ...) mean the code broke Temporal's rules rather than met bad input, so failing the task until the code
    is fixed stays their outcome.

    temporalio applies that test to an exception group (e.g. from ``asyncio.TaskGroup``) as a whole and never
    looks inside it, so a group fails the task unless the group itself is a failure exception. A group is
    therefore left to Temporal when the group itself is a ``TemporalError`` or a failure exception, or when
    it holds, at any depth, a ``TemporalError`` that is not itself a failure exception (one Temporal would
    fail the task for if it were raised alone). Any other group
    is dropped like any other unexpected exception, because re-raising it would wedge the workflow rather
    than fail it. That includes a group holding only failure exceptions, even a ``TemporalError`` declared
    as one, such as the ``AgentsWorkflowError`` that the OpenAI Agents plugin declares.
    """
    if isinstance(err, TemporalError) or workflow.is_failure_exception(err):
        return True
    if not isinstance(err, BaseExceptionGroup):
        return False
    # Walked iteratively rather than with BaseExceptionGroup.subgroup(), which recurses and calls the group's
    # derive(): anything raised here would replace the handler's exception and fail the task after all.
    pending: list[BaseException] = list(err.exceptions)
    while pending:
        exc = pending.pop()
        if isinstance(exc, TemporalError) and not workflow.is_failure_exception(exc):
            return True
        if isinstance(exc, BaseExceptionGroup):
            pending.extend(exc.exceptions)
    return False


def _log_dropped_signal(signal: str, err: Exception) -> None:
    # The signal's arguments are left out on purpose: the caller controls them and they can carry user content.
    info: workflow.Info | None = None
    try:
        info = workflow.info()
        # Handlers may import lazily while emitting (rich's does). Inside temporalio's default sandbox that can
        # raise RestrictedWorkflowAccessError and lose the record for every handler, so log with the sandbox's
        # restrictions lifted and imports passed through; outside a sandbox both are no-ops.
        with workflow.unsafe.sandbox_unrestricted(), workflow.unsafe.imports_passed_through():
            logger.error(
                "Dropped signal %r to workflow %s (type %s, run %s): its handler raised %s. Anything the handler "
                "did before raising is kept; the workflow keeps running and handles later signals.",
                signal,
                info.workflow_id,
                info.workflow_type,
                info.run_id,
                type(err).__qualname__,
                exc_info=err,
                extra={"signal_name": signal},
            )
    except Exception as log_err:
        # Failing to log must not fail the workflow task this interceptor exists to keep alive, but the drop must
        # not be silent either, so fall back to one bare stderr line (still without the signal's arguments).
        with contextlib.suppress(Exception):
            where = "" if info is None else f" to workflow {info.workflow_id} (run {info.run_id})"
            sys.stderr.write(
                f"agentex: dropped signal {signal!r}{where} after its handler raised {type(err).__qualname__}; "
                f"logging the drop failed with {type(log_err).__qualname__}\n"
            )
