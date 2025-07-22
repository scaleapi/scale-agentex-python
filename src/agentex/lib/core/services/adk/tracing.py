from typing import Any
from agentex.lib.core.tracing.tracer import AsyncTracer
from agentex.types.span import Span
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.utils.temporal import heartbeat_if_in_workflow

logger = make_logger(__name__)


class TracingService:
    def __init__(self, tracer: AsyncTracer):
        self._tracer = tracer

    async def start_span(
        self,
        trace_id: str,
        name: str,
        parent_id: str | None = None,
        input: list[Any] | dict[str, Any] | BaseModel | None = None,
        data: list[Any] | dict[str, Any] | BaseModel | None = None,
    ) -> Span | None:
        trace = self._tracer.trace(trace_id)
        async with trace.span(
            parent_id=parent_id,
            name=name,
            input=input or {},
            data=data,
        ) as span:
            heartbeat_if_in_workflow("start span")
            return span if span else None

    async def end_span(self, trace_id: str, span: Span) -> Span:
        trace = self._tracer.trace(trace_id)
        await trace.end_span(span)
        return span
