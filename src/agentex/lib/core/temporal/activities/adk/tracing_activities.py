from enum import Enum
from typing import Any

from temporalio import activity

from agentex.lib.core.services.adk.tracing import TracingService
from agentex.types.span import Span
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel

logger = make_logger(__name__)


class TracingActivityName(str, Enum):
    START_SPAN = "start-span"
    END_SPAN = "end-span"


class StartSpanParams(BaseModel):
    trace_id: str
    parent_id: str | None = None
    name: str
    input: list[Any] | dict[str, Any] | BaseModel | None = None
    data: list[Any] | dict[str, Any] | BaseModel | None = None


class EndSpanParams(BaseModel):
    trace_id: str
    span: Span


class TracingActivities:
    """
    Temporal activities for tracing (spans), ADK pattern.
    """

    def __init__(self, tracing_service: TracingService):
        self._tracing_service = tracing_service

    @activity.defn(name=TracingActivityName.START_SPAN)
    async def start_span(self, params: StartSpanParams) -> Span | None:
        return await self._tracing_service.start_span(
            trace_id=params.trace_id,
            parent_id=params.parent_id,
            name=params.name,
            input=params.input,
            data=params.data,
        )

    @activity.defn(name=TracingActivityName.END_SPAN)
    async def end_span(self, params: EndSpanParams) -> Span:
        return await self._tracing_service.end_span(
            trace_id=params.trace_id,
            span=params.span,
        )
