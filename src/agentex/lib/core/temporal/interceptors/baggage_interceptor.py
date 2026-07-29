"""Carries the caller-supplied ``end_user_id`` from a workflow into its activities.

For Temporal agents the ACP server only *starts* the workflow; the work runs in a
separate worker process, so a contextvar set at the ACP boundary never reaches the
code that creates spans. The value does survive that hop inside the workflow start
args and signal payloads, which is where the workflow-inbound half harvests it
from. Spans created by workflow code are covered too, since those dispatch through
a ``START_SPAN`` activity and so pass through the same activity-inbound hop.

Replay-safe: headers are derived only from start/signal args, with no clock or I/O.

Registered by default in ``AgentexWorker``; ``AGENTEX_DISABLE_TRACE_BAGGAGE``
(``1``/``true``/``yes``/``on``) disables it.
"""

from __future__ import annotations

import os
from typing import Any, override

from temporalio import workflow
from temporalio.worker import (
    Interceptor,
    HandleSignalInput,
    StartActivityInput,
    ExecuteActivityInput,
    ExecuteWorkflowInput,
    StartLocalActivityInput,
    ActivityInboundInterceptor,
    WorkflowInboundInterceptor,
    WorkflowOutboundInterceptor,
)
from temporalio.converter import default

from agentex.lib.utils.logging import make_logger
from agentex.lib.core.tracing.baggage import set_end_user_id, reset_end_user_id

logger = make_logger(__name__)

END_USER_ID_HEADER = "agentex-end-user-id"
_WORKFLOW_ATTR = "_agentex_end_user_id"
DISABLE_TRACE_BAGGAGE_ENV = "AGENTEX_DISABLE_TRACE_BAGGAGE"


def trace_baggage_disabled() -> bool:
    raw = os.environ.get(DISABLE_TRACE_BAGGAGE_ENV, "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _extract_end_user_id(arg: Any) -> str | None:
    # Args arrive as the params model or as its dumped dict, depending on how the
    # caller serialized them.
    if arg is None:
        return None
    value = arg.get("end_user_id") if isinstance(arg, dict) else getattr(arg, "end_user_id", None)
    return value if isinstance(value, str) and value else None


class TraceBaggageInterceptor(Interceptor):
    """Threads the caller-supplied end user from workflow start args to activities."""

    def __init__(self) -> None:
        self._payload_converter = default().payload_converter

    @override
    def intercept_activity(self, next: ActivityInboundInterceptor) -> ActivityInboundInterceptor:
        return _TraceBaggageActivityInboundInterceptor(next, self._payload_converter)

    @override
    def workflow_interceptor_class(self, input: Any) -> type[WorkflowInboundInterceptor] | None:  # noqa: ARG002
        return _TraceBaggageWorkflowInboundInterceptor


class _TraceBaggageWorkflowInboundInterceptor(WorkflowInboundInterceptor):
    """Harvests the end user off inbound workflow args and signal args."""

    @override
    async def execute_workflow(self, input: ExecuteWorkflowInput) -> Any:
        self._stash(input.args[0] if input.args else None)
        return await self.next.execute_workflow(input)

    @override
    async def handle_signal(self, input: HandleSignalInput) -> None:
        # Signals (e.g. event/send) carry their own end user, which may differ
        # from the one that created the task. Last one in wins so the activities
        # a signal triggers are attributed to the caller that triggered them.
        self._stash(input.args[0] if input.args else None)
        return await self.next.handle_signal(input)

    def _stash(self, arg: Any) -> None:
        end_user_id = _extract_end_user_id(arg)
        if end_user_id is None:
            return
        try:
            setattr(workflow.instance(), _WORKFLOW_ATTR, end_user_id)
        except Exception as exc:
            logger.debug(f"Could not stash end_user_id on the workflow instance: {exc}")

    @override
    def init(self, outbound: WorkflowOutboundInterceptor) -> None:
        self.next.init(_TraceBaggageWorkflowOutboundInterceptor(outbound, default().payload_converter))


class _TraceBaggageWorkflowOutboundInterceptor(WorkflowOutboundInterceptor):
    """Copies the stashed end user into activity headers."""

    def __init__(self, next: WorkflowOutboundInterceptor, payload_converter: Any) -> None:
        super().__init__(next)
        self._payload_converter = payload_converter

    @override
    def start_activity(self, input: StartActivityInput) -> workflow.ActivityHandle[Any]:
        self._add_header(input)
        return self.next.start_activity(input)

    @override
    def start_local_activity(self, input: StartLocalActivityInput) -> workflow.ActivityHandle[Any]:
        self._add_header(input)
        return self.next.start_local_activity(input)

    def _add_header(self, input: StartActivityInput | StartLocalActivityInput) -> None:
        try:
            end_user_id = getattr(workflow.instance(), _WORKFLOW_ATTR, None)
            if not end_user_id:
                return
            headers = dict(input.headers or {})
            headers[END_USER_ID_HEADER] = self._payload_converter.to_payload(end_user_id)
            input.headers = headers
        except Exception as exc:
            logger.debug(f"Could not add end_user_id to activity headers: {exc}")


class _TraceBaggageActivityInboundInterceptor(ActivityInboundInterceptor):
    """Decodes the header into the tracing baggage contextvar for the activity."""

    def __init__(self, next: ActivityInboundInterceptor, payload_converter: Any) -> None:
        super().__init__(next)
        self._payload_converter = payload_converter

    @override
    async def execute_activity(self, input: ExecuteActivityInput) -> Any:
        end_user_id: str | None = None
        if input.headers and END_USER_ID_HEADER in input.headers:
            try:
                end_user_id = self._payload_converter.from_payload(input.headers[END_USER_ID_HEADER], str)
            except Exception as exc:
                logger.debug(f"Could not decode the end_user_id activity header: {exc}")

        if end_user_id is None:
            return await self.next.execute_activity(input)

        token = set_end_user_id(end_user_id)
        try:
            return await self.next.execute_activity(input)
        finally:
            reset_end_user_id(token)
