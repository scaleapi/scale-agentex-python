from typing import Any, Dict, override

from agentex import Agentex, AsyncAgentex
from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.tracing.processors.tracing_processor_interface import (
    AsyncTracingProcessor,
    SyncTracingProcessor,
)
from agentex.types.span import Span
from agentex.lib.types.tracing import AgentexTracingProcessorConfig


class AgentexSyncTracingProcessor(SyncTracingProcessor):
    def __init__(self, config: AgentexTracingProcessorConfig):
        self.client = Agentex()

    @override
    def on_span_start(self, span: Span) -> None:
        self.client.spans.create(
            name=span.name,
            start_time=span.start_time,
            end_time=span.end_time,
            trace_id=span.trace_id,
            id=span.id,
            data=span.data,
            input=span.input,
            output=span.output,
            parent_id=span.parent_id,
        )

    @override
    def on_span_end(self, span: Span) -> None:
        update: Dict[str, Any] = {}
        if span.trace_id:
            update["trace_id"] = span.trace_id
        if span.name:
            update["name"] = span.name
        if span.parent_id:
            update["parent_id"] = span.parent_id
        if span.start_time:
            update["start_time"] = span.start_time.isoformat()
        if span.end_time is not None:
            update["end_time"] = span.end_time.isoformat()
        if span.input is not None:
            update["input"] = span.input
        if span.output is not None:
            update["output"] = span.output
        if span.data is not None:
            update["data"] = span.data

        self.client.spans.update(
            span.id,
            **span.model_dump(
                mode="json",
                exclude={"id"},
                exclude_defaults=True,
                exclude_none=True,
                exclude_unset=True,
            ),
        )

    @override
    def shutdown(self) -> None:
        pass


class AgentexAsyncTracingProcessor(AsyncTracingProcessor):
    def __init__(self, config: AgentexTracingProcessorConfig):
        self.client = create_async_agentex_client()

    @override
    async def on_span_start(self, span: Span) -> None:
        await self.client.spans.create(
            name=span.name,
            start_time=span.start_time,
            end_time=span.end_time,
            id=span.id,
            trace_id=span.trace_id,
            parent_id=span.parent_id,
            input=span.input,
            output=span.output,
            data=span.data,
        )

    @override
    async def on_span_end(self, span: Span) -> None:
        update: Dict[str, Any] = {}
        if span.trace_id:
            update["trace_id"] = span.trace_id
        if span.name:
            update["name"] = span.name
        if span.parent_id:
            update["parent_id"] = span.parent_id
        if span.start_time:
            update["start_time"] = span.start_time.isoformat()
        if span.end_time:
            update["end_time"] = span.end_time.isoformat()
        if span.input:
            update["input"] = span.input
        if span.output:
            update["output"] = span.output
        if span.data:
            update["data"] = span.data

        await self.client.spans.update(
            span.id,
            **span.model_dump(
                mode="json",
                exclude={"id"},
                exclude_defaults=True,
                exclude_none=True,
                exclude_unset=True,
            ),
        )

    @override
    async def shutdown(self) -> None:
        pass
