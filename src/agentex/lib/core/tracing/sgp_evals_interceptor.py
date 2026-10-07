"""Carry an eval task's span attrs from its Temporal workflow memo into the worker's activities.

Spans are emitted by activities in the worker process, which never sees the ACP
server's task. The ACP server puts the attrs in the workflow memo, the outbound
interceptor copies them onto each activity's headers, and the activity
interceptor registers them for the task so the SGP processor can stamp spans.
Non-eval workflows have no memo entry and get no header.
"""

from __future__ import annotations

from typing import Any, override

from temporalio import activity, workflow
from temporalio.worker import (
    Interceptor,
    StartActivityInput,
    ExecuteActivityInput,
    ActivityInboundInterceptor,
    WorkflowInboundInterceptor,
    WorkflowOutboundInterceptor,
)
from temporalio.converter import default

from agentex.lib.utils.logging import make_logger
from agentex.lib.core.tracing.sgp_evals import MEMO_KEY, register_task

logger = make_logger(__name__)

ATTRS_HEADER = "sgp-evals-span-attrs"
_converter = default().payload_converter


class SGPEvalsInterceptor(Interceptor):
    @override
    def intercept_activity(self, next: ActivityInboundInterceptor) -> ActivityInboundInterceptor:
        return _ActivityInbound(next)

    @override
    def workflow_interceptor_class(self, input: Any) -> type[WorkflowInboundInterceptor] | None:
        return _WorkflowInbound


class _WorkflowInbound(WorkflowInboundInterceptor):
    @override
    def init(self, outbound: WorkflowOutboundInterceptor) -> None:
        super().init(_WorkflowOutbound(outbound))


class _WorkflowOutbound(WorkflowOutboundInterceptor):
    @override
    def start_activity(self, input: StartActivityInput) -> workflow.ActivityHandle[Any]:
        attrs = workflow.memo_value(MEMO_KEY, default=None)
        if isinstance(attrs, dict) and attrs:
            input.headers = {**input.headers, ATTRS_HEADER: _converter.to_payload(attrs)}
        return super().start_activity(input)


class _ActivityInbound(ActivityInboundInterceptor):
    @override
    async def execute_activity(self, input: ExecuteActivityInput) -> Any:
        payload = input.headers.get(ATTRS_HEADER)
        # The workflow id is the task id (see TemporalTaskService.submit_task).
        task_id = activity.info().workflow_id
        if payload is not None and task_id:
            try:
                register_task(task_id, _converter.from_payload(payload, dict))
            except Exception:
                logger.warning("failed to read sgp evals span attrs from activity headers", exc_info=True)
        return await super().execute_activity(input)
