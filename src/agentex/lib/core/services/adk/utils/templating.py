from datetime import datetime
from typing import Any

from jinja2 import BaseLoader, Environment

from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.lib.utils.temporal import heartbeat_if_in_workflow

# Create a Jinja environment
JINJA_ENV = Environment(
    loader=BaseLoader(),
    trim_blocks=True,
    lstrip_blocks=True,
    extensions=["jinja2.ext.do"],
)


class TemplatingService:
    def __init__(self, tracer: AsyncTracer | None = None):
        self.tracer = tracer

    async def render_jinja(
        self,
        template: str,
        variables: dict[str, Any],
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> str:
        """
        Activity that renders a Jinja template with the provided data.

        Args:
            template: The template string to render.
            variables: The variables to render the template with.
            trace_id: The trace ID for tracing.
            parent_span_id: The parent span ID for tracing.

        Returns:
            The rendered template as a string
        """
        trace = self.tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_span_id,
            name="render_jinja",
            input={"template": template, "variables": variables},
        ) as span:
            heartbeat_if_in_workflow("render jinja")
            global_variables = {
                "datetime": datetime,
            }
            jinja_template = JINJA_ENV.from_string(template, globals=global_variables)
            try:
                rendered_template = jinja_template.render(variables)
                if span:
                    span.output = {"jinja_output": rendered_template}
                return rendered_template
            except Exception as e:
                raise ValueError(f"Error rendering Jinja template: {str(e)}") from e
