"""
Temporal context interceptors for threading runtime context through workflows and activities.

This module provides interceptors that pass task_id, trace_id, and parent_span_id from
workflows to activities via headers, making them available via ContextVars for models
to use for streaming, tracing, or other purposes.
"""

import logging
from typing import Any, Type, Optional, override
from contextvars import ContextVar

from temporalio import workflow
from temporalio.worker import (
    Interceptor,
    StartActivityInput,
    ExecuteActivityInput,
    ExecuteWorkflowInput,
    ActivityInboundInterceptor,
    WorkflowInboundInterceptor,
    WorkflowOutboundInterceptor,
)
from temporalio.converter import default

# Set up logging
logger = logging.getLogger("context.interceptor")

# Global context variables that models can read
# These are thread-safe and work across async boundaries
streaming_task_id: ContextVar[Optional[str]] = ContextVar('streaming_task_id', default=None)
streaming_trace_id: ContextVar[Optional[str]] = ContextVar('streaming_trace_id', default=None)
streaming_parent_span_id: ContextVar[Optional[str]] = ContextVar('streaming_parent_span_id', default=None)

# Header keys for passing context
TASK_ID_HEADER = "context-task-id"
TRACE_ID_HEADER = "context-trace-id"
PARENT_SPAN_ID_HEADER = "context-parent-span-id"

class ContextInterceptor(Interceptor):
    """Main interceptor that enables context threading through Temporal."""

    def __init__(self):
        self._payload_converter = default().payload_converter
        logger.info("[ContextInterceptor] Initialized")

    @override
    def intercept_activity(self, next: ActivityInboundInterceptor) -> ActivityInboundInterceptor:
        """Create activity interceptor to read context from headers."""
        return ContextActivityInboundInterceptor(next, self._payload_converter)

    @override
    def workflow_interceptor_class(self, _input: Any) -> Optional[Type[WorkflowInboundInterceptor]]:
        """Return workflow interceptor class."""
        return ContextWorkflowInboundInterceptor


class ContextWorkflowInboundInterceptor(WorkflowInboundInterceptor):
    """Workflow interceptor that creates the outbound interceptor."""

    def __init__(self, next: WorkflowInboundInterceptor):
        super().__init__(next)
        self._payload_converter = default().payload_converter

    @override
    async def execute_workflow(self, input: ExecuteWorkflowInput) -> Any:
        """Execute workflow - just pass through."""
        return await self.next.execute_workflow(input)

    @override
    def init(self, outbound: WorkflowOutboundInterceptor) -> None:
        """Initialize with our custom outbound interceptor."""
        self.next.init(ContextWorkflowOutboundInterceptor(
            outbound, self._payload_converter
        ))


class ContextWorkflowOutboundInterceptor(WorkflowOutboundInterceptor):
    """Outbound interceptor that adds task_id to activity headers."""

    def __init__(self, next, payload_converter):
        super().__init__(next)
        self._payload_converter = payload_converter

    @override
    def start_activity(self, input: StartActivityInput) -> workflow.ActivityHandle:
        """Add task_id, trace_id, and parent_span_id to headers when starting model activities."""

        # Only add headers for invoke_model_activity calls
        activity_name = str(input.activity) if hasattr(input, 'activity') else ""

        if "invoke_model_activity" in activity_name or "invoke-model-activity" in activity_name:
            # Get task_id, trace_id, and parent_span_id from workflow instance instead of inbound interceptor
            try:
                workflow_instance = workflow.instance()
                task_id = getattr(workflow_instance, '_task_id', None)
                trace_id = getattr(workflow_instance, '_trace_id', None)
                parent_span_id = getattr(workflow_instance, '_parent_span_id', None)

                if task_id and trace_id and parent_span_id:
                    # Initialize headers if needed
                    if not input.headers:
                        input.headers = {}

                    # Add task_id to headers
                    input.headers[TASK_ID_HEADER] = self._payload_converter.to_payload(task_id)  # type: ignore[index]
                    input.headers[TRACE_ID_HEADER] = self._payload_converter.to_payload(trace_id)  # type: ignore[index]
                    input.headers[PARENT_SPAN_ID_HEADER] = self._payload_converter.to_payload(parent_span_id)  # type: ignore[index]
                    logger.debug(f"[OutboundInterceptor] Added task_id, trace_id, and parent_span_id to activity headers: {task_id}, {trace_id}, {parent_span_id}")
                else:
                    logger.warning("[OutboundInterceptor] No _task_id, _trace_id, or _parent_span_id found in workflow instance")
            except Exception as e:
                logger.error(f"[OutboundInterceptor] Failed to get task_id, trace_id, or parent_span_id from workflow instance: {e}")

        return self.next.start_activity(input)


class ContextActivityInboundInterceptor(ActivityInboundInterceptor):
    """Activity interceptor that extracts task_id, trace_id, and parent_span_id from headers and sets context variables."""

    def __init__(self, next, payload_converter):
        super().__init__(next)
        self._payload_converter = payload_converter

    @override
    async def execute_activity(self, input: ExecuteActivityInput) -> Any:
        """Extract task_id, trace_id, and parent_span_id from headers and set context variables."""

        # Extract task_id from headers if present
        if input.headers and TASK_ID_HEADER in input.headers:
            task_id_value = self._payload_converter.from_payload(
                input.headers[TASK_ID_HEADER], str
            )
            trace_id_value = self._payload_converter.from_payload(
                input.headers[TRACE_ID_HEADER], str
            )
            parent_span_id_value = self._payload_converter.from_payload(
                input.headers[PARENT_SPAN_ID_HEADER], str
            )

            # P THIS IS THE KEY PART - Set the context variable!
            # This makes task_id available to TemporalStreamingModel.get_response()
            streaming_task_id.set(task_id_value)
            streaming_trace_id.set(trace_id_value)
            streaming_parent_span_id.set(parent_span_id_value)
            logger.info(f"[ActivityInterceptor] Set task_id, trace_id, and parent_span_id in context: {task_id_value}, {trace_id_value}, {parent_span_id_value}")
        else:
            logger.debug("[ActivityInterceptor] No task_id, trace_id, or parent_span_id in headers")

        try:
            # Execute the activity
            # The TemporalStreamingModel can now read streaming_task_id.get()
            result = await self.next.execute_activity(input)
            return result
        finally:
            # Clean up context after activity
            streaming_task_id.set(None)
            streaming_trace_id.set(None)
            streaming_parent_span_id.set(None)
            logger.debug("[ActivityInterceptor] Cleared task_id, trace_id, and parent_span_id from context")

