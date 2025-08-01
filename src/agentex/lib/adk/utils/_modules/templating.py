from datetime import timedelta
from typing import Any

from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from temporalio.common import RetryPolicy

from agentex import AsyncAgentex
from agentex.lib.core.services.adk.utils.templating import TemplatingService
from agentex.lib.core.temporal.activities.activity_helpers import ActivityHelpers
from agentex.lib.core.temporal.activities.adk.utils.templating_activities import (
    JinjaActivityName,
    RenderJinjaParams,
)
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import in_temporal_workflow

logger = make_logger(__name__)

DEFAULT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


class TemplatingModule:
    """
    Module for managing templating operations in Agentex.

    This interface provides high-level methods for rendering Jinja templates, abstracting away
    the underlying activity and workflow execution. It supports both synchronous and asynchronous
    (Temporal workflow) contexts.
    """

    def __init__(
        self,
        templating_service: TemplatingService | None = None,
    ):
        """
        Initialize the templating interface.

        Args:
            templating_service (Optional[TemplatingService]): Optional pre-configured templating service. If None, will be auto-initialized.
        """
        if templating_service is None:
            agentex_client = create_async_agentex_client()
            tracer = AsyncTracer(agentex_client)
            self._templating_service = TemplatingService(tracer=tracer)
        else:
            self._templating_service = templating_service

    async def render_jinja(
        self,
        trace_id: str,
        template: str,
        variables: dict[str, Any],
        parent_span_id: str | None = None,
        start_to_close_timeout: timedelta = timedelta(seconds=10),
        heartbeat_timeout: timedelta = timedelta(seconds=10),
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> str:
        """
        Render a Jinja template.

        Args:
            trace_id (str): Unique identifier for tracing and correlation.
            template (str): The Jinja template string to render.
            variables (Dict[str, Any]): Variables to use in the template.
            parent_span_id (Optional[str]): Optional parent span for tracing.
            start_to_close_timeout (timedelta): Maximum time allowed for the operation.
            heartbeat_timeout (timedelta): Maximum time between heartbeats.
            retry_policy (RetryPolicy): Policy for retrying failed operations.

        Returns:
            str: The rendered template as a string.
        """
        render_jinja_params = RenderJinjaParams(
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            template=template,
            variables=variables,
        )
        if in_temporal_workflow():
            return await ActivityHelpers.execute_activity(
                activity_name=JinjaActivityName.RENDER_JINJA,
                request=render_jinja_params,
                response_type=str,
                start_to_close_timeout=start_to_close_timeout,
                heartbeat_timeout=heartbeat_timeout,
                retry_policy=retry_policy,
            )
        else:
            return await self._templating_service.render_jinja(
                template=template,
                variables=variables,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )
