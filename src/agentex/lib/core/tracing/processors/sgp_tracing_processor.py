from typing import override

import scale_gp_beta.lib.tracing as tracing
from scale_gp_beta import AsyncSGPClient, SGPClient
from scale_gp_beta.lib.tracing import create_span, flush_queue
from scale_gp_beta.lib.tracing.span import Span as SGPSpan

from agentex.lib.core.tracing.processors.tracing_processor_interface import (
    AsyncTracingProcessor,
    SyncTracingProcessor,
)
from agentex.types.span import Span
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class SGPSyncTracingProcessor(SyncTracingProcessor):
    def __init__(self, config: SGPTracingProcessorConfig):
        disabled = config.sgp_api_key == "" or config.sgp_account_id == ""
        tracing.init(
            SGPClient(api_key=config.sgp_api_key, account_id=config.sgp_account_id),
            disabled=disabled,
        )
        self._spans: dict[str, SGPSpan] = {}

    @override
    def on_span_start(self, span: Span) -> None:
        sgp_span = create_span(
            name=span.name,
            span_id=span.id,
            parent_id=span.parent_id,
            trace_id=span.trace_id,
            input=span.input,
            output=span.output,
            metadata=span.data,
        )
        sgp_span.start_time = span.start_time.isoformat()
        sgp_span.flush(blocking=False)

        self._spans[span.id] = sgp_span

    @override
    def on_span_end(self, span: Span) -> None:
        sgp_span = self._spans.get(span.id)
        if sgp_span is None:
            logger.warning(
                f"Span {span.id} not found in stored spans, skipping span end"
            )
            return

        sgp_span.output = span.output
        sgp_span.metadata = span.data
        sgp_span.end_time = span.end_time.isoformat()
        sgp_span.flush(blocking=False)

    @override
    def shutdown(self) -> None:
        self._spans.clear()
        flush_queue()


class SGPAsyncTracingProcessor(AsyncTracingProcessor):
    def __init__(self, config: SGPTracingProcessorConfig):
        self.disabled = config.sgp_api_key == "" or config.sgp_account_id == ""
        self._spans: dict[str, SGPSpan] = {}
        self.sgp_async_client = (
            AsyncSGPClient(api_key=config.sgp_api_key, account_id=config.sgp_account_id)
            if not self.disabled
            else None
        )

    @override
    async def on_span_start(self, span: Span) -> None:
        sgp_span = create_span(
            name=span.name,
            span_id=span.id,
            parent_id=span.parent_id,
            trace_id=span.trace_id,
            input=span.input,
            output=span.output,
            metadata=span.data,
        )
        sgp_span.start_time = span.start_time.isoformat()

        if self.disabled:
            return
        await self.sgp_async_client.spans.upsert_batch(
            items=[sgp_span.to_request_params()]
        )

        self._spans[span.id] = sgp_span

    @override
    async def on_span_end(self, span: Span) -> None:
        sgp_span = self._spans.get(span.id)
        if sgp_span is None:
            logger.warning(
                f"Span {span.id} not found in stored spans, skipping span end"
            )
            return

        sgp_span.output = span.output
        sgp_span.metadata = span.data
        sgp_span.end_time = span.end_time.isoformat()

        if self.disabled:
            return
        await self.sgp_async_client.spans.upsert_batch(
            items=[sgp_span.to_request_params()]
        )

    @override
    async def shutdown(self) -> None:
        await self.sgp_async_client.spans.upsert_batch(
            items=[sgp_span.to_request_params() for sgp_span in self._spans.values()]
        )
        self._spans.clear()
