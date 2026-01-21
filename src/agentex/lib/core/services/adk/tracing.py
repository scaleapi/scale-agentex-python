from __future__ import annotations

from typing import Any

from agentex.types.span import Span
from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.temporal import heartbeat_if_in_workflow
from agentex.lib.utils.model_utils import BaseModel
from agentex.lib.core.tracing.tracer import AsyncTracer

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
        span = await trace.start_span(
            name=name,
            parent_id=parent_id,
            input=input or {},
            data=data,
        )
        heartbeat_if_in_workflow("start span")
        return span

    async def end_span(self, trace_id: str, span: Span) -> Span:
        trace = self._tracer.trace(trace_id)
        await trace.end_span(span)
        return span
