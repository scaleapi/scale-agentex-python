from __future__ import annotations

from typing import cast, override

import scale_gp_beta.lib.tracing as tracing
from scale_gp_beta import SGPClient, AsyncSGPClient
from scale_gp_beta.lib.tracing import create_span, flush_queue
from scale_gp_beta.lib.tracing.span import Span as SGPSpan

from agentex.types.span import Span
from agentex.lib.types.tracing import SGPTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.core.tracing.processors.tracing_processor_interface import (
    SyncTracingProcessor,
    AsyncTracingProcessor,
)

logger = make_logger(__name__)


def _get_span_type(span: Span) -> str:
    """Read span_type from span.data['__span_type__'], defaulting to STANDALONE."""
    if isinstance(span.data, dict):
        value = span.data.get("__span_type__", "STANDALONE")
        return str(value)
    return "STANDALONE"


def _add_source_to_span(span: Span, env_vars: EnvironmentVariables) -> None:
    if span.data is None:
        span.data = {}
    if isinstance(span.data, dict):
        span.data["__source__"] = "agentex"
        if env_vars.ACP_TYPE is not None:
            span.data["__acp_type__"] = env_vars.ACP_TYPE
        if env_vars.AGENT_NAME is not None:
            span.data["__agent_name__"] = env_vars.AGENT_NAME
        if env_vars.AGENT_ID is not None:
            span.data["__agent_id__"] = env_vars.AGENT_ID


def _build_sgp_span(span: Span, env_vars: EnvironmentVariables) -> SGPSpan:
    """Build an SGPSpan from an agentex Span. Idempotent on span_id at the SGP backend."""
    _add_source_to_span(span, env_vars)
    sgp_span = cast(
        SGPSpan,
        create_span(
            name=span.name,
            span_type=_get_span_type(span),
            span_id=span.id,
            parent_id=span.parent_id,
            trace_id=span.trace_id,
            input=span.input,
            output=span.output,
            metadata=span.data,
        ),
    )
    sgp_span.start_time = span.start_time.isoformat()  # type: ignore[union-attr]
    return sgp_span


class SGPSyncTracingProcessor(SyncTracingProcessor):
    def __init__(self, config: SGPTracingProcessorConfig):
        disabled = config.sgp_api_key == "" or config.sgp_account_id == ""
        tracing.init(
            SGPClient(
                api_key=config.sgp_api_key,
                account_id=config.sgp_account_id,
                base_url=config.sgp_base_url,
            ),
            disabled=disabled,
        )
        self.env_vars = EnvironmentVariables.refresh()

    @override
    def on_span_start(self, span: Span) -> None:
        sgp_span = _build_sgp_span(span, self.env_vars)
        sgp_span.flush(blocking=False)

    @override
    def on_span_end(self, span: Span) -> None:
        sgp_span = _build_sgp_span(span, self.env_vars)
        sgp_span.end_time = span.end_time.isoformat()  # type: ignore[union-attr]
        sgp_span.flush(blocking=False)

    @override
    def shutdown(self) -> None:
        flush_queue()


class SGPAsyncTracingProcessor(AsyncTracingProcessor):
    def __init__(self, config: SGPTracingProcessorConfig):
        self.disabled = config.sgp_api_key == "" or config.sgp_account_id == ""
        import httpx

        # Disable keepalive so each HTTP call gets a fresh TCP connection,
        # avoiding "bound to a different event loop" errors in sync-ACP.
        self.sgp_async_client = (
            AsyncSGPClient(
                api_key=config.sgp_api_key,
                account_id=config.sgp_account_id,
                base_url=config.sgp_base_url,
                http_client=httpx.AsyncClient(
                    limits=httpx.Limits(max_keepalive_connections=0),
                ),
            )
            if not self.disabled
            else None
        )
        self.env_vars = EnvironmentVariables.refresh()

    @override
    async def on_span_start(self, span: Span) -> None:
        await self.on_spans_start([span])

    @override
    async def on_span_end(self, span: Span) -> None:
        await self.on_spans_end([span])

    @override
    async def on_spans_start(self, spans: list[Span]) -> None:
        if not spans:
            return

        sgp_spans = [_build_sgp_span(span, self.env_vars) for span in spans]

        if self.disabled:
            logger.warning("SGP is disabled, skipping span upsert")
            return
        await self.sgp_async_client.spans.upsert_batch(  # type: ignore[union-attr]
            items=[s.to_request_params() for s in sgp_spans]
        )

    @override
    async def on_spans_end(self, spans: list[Span]) -> None:
        if not spans:
            return

        sgp_spans: list[SGPSpan] = []
        for span in spans:
            sgp_span = _build_sgp_span(span, self.env_vars)
            sgp_span.end_time = span.end_time.isoformat()  # type: ignore[union-attr]
            sgp_spans.append(sgp_span)

        if self.disabled:
            return
        await self.sgp_async_client.spans.upsert_batch(  # type: ignore[union-attr]
            items=[s.to_request_params() for s in sgp_spans]
        )

    @override
    async def shutdown(self) -> None:
        pass
