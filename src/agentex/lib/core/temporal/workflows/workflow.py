from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable
from datetime import timedelta

from temporalio import workflow

from agentex.protocol.acp import SendEventParams, CreateTaskParams
from agentex.lib.utils.logging import make_logger
from agentex.lib.core.temporal.types.workflow import SignalName

logger = make_logger(__name__)


class BaseWorkflow(ABC):
    def __init__(
        self,
        display_name: str,
    ):
        self.display_name = display_name

    @abstractmethod
    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    async def on_task_event_send(self, params: SendEventParams) -> None:
        raise NotImplementedError

    @abstractmethod
    async def on_task_create(self, params: CreateTaskParams) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Continue-as-new lifecycle helpers                                   #
    #                                                                     #
    # These let a long-lived chat/session workflow recycle its event      #
    # history so it can stay open indefinitely without hitting Temporal's #
    # ~50k-event / 50MB history limit. They are OPT-IN: an agent gets     #
    # recycling only by calling `run_until_complete` from its             #
    # `@workflow.run` instead of the usual indefinite `wait_condition`.   #
    # The SDK owns the hard Temporal mechanics (recycle decision and      #
    # draining in-flight handlers before the continue_as_new call).       #
    # Restoring state after a recycle is the AGENT's job and is           #
    # framework-specific (rebuild from `adk.messages`, an `adk.state`     #
    # snapshot, or a framework's own memory); that lands per-integration  #
    # in follow-up PRs. The 000_hello_acp example shows the minimal       #
    # stateless adoption that needs no restoration.                       #
    # ------------------------------------------------------------------ #

    def should_continue_as_new(self) -> bool:
        """Whether this run should recycle its event history via continue-as-new.

        True when Temporal suggests it: ``is_continue_as_new_suggested()`` fires as
        the event history approaches the server's size/count limit, so we let
        Temporal own the threshold rather than configuring one ourselves.

        This reads only a deterministic ``workflow.info()`` value and emits no
        commands, so it is safe to use directly as a ``workflow.wait_condition``
        predicate, e.g.::

            await workflow.wait_condition(
                lambda: self._complete_task or self.should_continue_as_new()
            )
        """
        return workflow.info().is_continue_as_new_suggested()

    async def drain_and_continue_as_new(
        self,
        *args: Any,
        is_complete: Callable[[], bool] | None = None,
    ) -> None:
        """Drain in-flight signal handlers, then continue-as-new.

        Call this from the agent's ``@workflow.run`` once the run loop wakes for a
        recycle (see :meth:`should_continue_as_new`). ``args`` are forwarded
        verbatim to ``workflow.continue_as_new`` and become the new run's input, so
        pass whatever your ``@workflow.run`` signature expects — typically the
        original ``CreateTaskParams`` (the new run keeps the same workflow id / task
        id and re-hydrates its state from ``adk.state``).

        IMPORTANT: keep your data OUTSIDE workflow state BEFORE calling this —
        messages in ``adk.messages`` and any other state in ``adk.state``.
        In-workflow attributes do NOT survive the recycle; only the forwarded
        ``args`` do.

        Waits on ``all_handlers_finished`` first so an in-flight turn (a signal
        handler still running an activity) is never lost or duplicated across the
        recycle boundary. ``workflow.continue_as_new`` raises to end the run, so
        this never returns normally — EXCEPT when ``is_complete`` is given and
        returns True after draining: a completion signal can arrive while we wait
        for the drain, and the recycled run would start fresh (losing that
        completion), so in that case we return without recycling and let the caller
        finish.
        """
        # Don't recycle until any signal handler still running has finished, so a
        # message mid-flight at the boundary is carried into the next run intact.
        await workflow.wait_condition(workflow.all_handlers_finished)
        # A completion signal may have landed during the drain — re-check before
        # recycling so a workflow that should finish isn't kept open by the recycle.
        if is_complete is not None and is_complete():
            return
        logger.info(
            "Recycling workflow via continue-as-new "
            f"(history_length={workflow.info().get_current_history_length()}, "
            f"run_id={workflow.info().run_id})"
        )
        workflow.continue_as_new(*args)

    async def run_until_complete(
        self,
        *continue_as_new_args: Any,
        is_complete: Callable[[], bool],
        timeout: timedelta | None = None,
    ) -> None:
        """Keep the workflow open to field events, recycling history as needed.

        Drop-in replacement for the usual ``await workflow.wait_condition(
        lambda: self._complete_task, timeout=None)`` at the end of an agent's
        ``@workflow.run``. ``is_complete`` is a no-arg predicate (typically
        ``lambda: self._complete_task``); ``continue_as_new_args`` are forwarded to
        continue-as-new on recycle (typically the original ``CreateTaskParams``).

        Adopting this method IS the opt-in to recycling — there is no flag. An agent
        that keeps the old indefinite ``wait_condition`` never recycles.

        ``timeout`` is an optional cap on how long to wait with no progress; it
        defaults to None = wait indefinitely (the usual case — Temporal can keep huge
        numbers of idle workflows open). The broader workflow-level lifetime cap is
        the execution timeout (``WORKFLOW_EXECUTION_TIMEOUT_SECONDS``, also infinite
        by default). On ``timeout`` expiry ``wait_condition`` raises
        ``asyncio.TimeoutError`` like before.

        Persist anything you need across a recycle OUTSIDE workflow state first —
        messages in ``adk.messages``, other state in ``adk.state`` — and rebuild it
        at the top of ``@workflow.run``.
        """
        while True:
            await workflow.wait_condition(
                lambda: is_complete() or self.should_continue_as_new(),
                timeout=timeout,
            )
            if is_complete():
                return
            # Drains in-flight handlers, then continue-as-new (raises; never
            # returns) — UNLESS a completion signal arrived during the drain, in
            # which case it returns here and the next loop iteration completes.
            await self.drain_and_continue_as_new(
                *continue_as_new_args, is_complete=is_complete
            )
            if is_complete():
                return

    def is_continued_run(self) -> bool:
        """Whether this run was produced by a continue-as-new from a prior run.

        True only on a recycled run (``workflow.info().continued_run_id`` is set),
        False on the original run a client created. Use it in ``@workflow.run`` to
        gate one-time prologue work that must NOT repeat on every recycle — e.g. a
        welcome message, or rehydrating state only when there's something to restore.
        The recycled run re-enters ``@workflow.run`` from the top, so anything not
        gated here runs again on each history rollover.
        """
        return workflow.info().continued_run_id is not None
