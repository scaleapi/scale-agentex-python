from enum import Enum
from typing import Any

from temporalio import activity

from agentex.lib.core.services.adk.utils.templating import TemplatingService
from agentex.lib.types.tracing import BaseModelWithTraceParams


class JinjaActivityName(str, Enum):
    RENDER_JINJA = "render-jinja"


class RenderJinjaParams(BaseModelWithTraceParams):
    """Parameters for the Jinja activity"""

    template: str
    variables: dict[str, Any]


class TemplatingActivities:
    def __init__(self, templating_service: TemplatingService):
        self.templating_service = templating_service

    @activity.defn(name=JinjaActivityName.RENDER_JINJA)
    async def render_jinja(self, params: RenderJinjaParams) -> str:
        """
        Activity that renders a Jinja template with the provided data.

        Args:
            params: JinjaParams containing the data and template string

        Returns:
            The rendered template as a string
        """
        return await self.templating_service.render_jinja(
            template=params.template,
            variables=params.variables,
            trace_id=params.trace_id,
            parent_span_id=params.parent_span_id,
        )
