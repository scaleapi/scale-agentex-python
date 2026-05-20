from __future__ import annotations

import asyncio
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
        self._config = config
        # Per-event-loop client cache.  httpx.AsyncClient ties its connection
        # pool to the loop it was created on; in sync-ACP / streaming contexts
        # the active loop can change between requests.  Keying by loop id lets
        # us keep keepalive on within each loop while staying safe across
        # loops.  The construction can also happen at module import time when
        # no loop is running, so we have to defer it until the first call.
        self._clients_by_loop_id: dict[int, AsyncSGPClient] = {}
        self.env_vars = EnvironmentVariables.refresh()

    def _build_client(self) -> AsyncSGPClient:
        import httpx

        return AsyncSGPClient(
            api_key=self._config.sgp_api_key,
            account_id=self._config.sgp_account_id,
            base_url=self._config.sgp_base_url,
            # Keepalive ON: connections are reused within a single event loop,
            # which removes the TLS-handshake-per-span penalty observed under
            # load.  Cross-loop safety is preserved by the per-loop cache.
            http_client=httpx.AsyncClient(
                limits=httpx.Limits(max_keepalive_connections=20),
            ),
        )

    def _get_client(self) -> AsyncSGPClient | None:
        """Return the AsyncSGPClient bound to the current event loop, creating
        one on first use.  Returns None when the processor is disabled."""
        if self.disabled:
            return None
        try:
            loop_id = id(asyncio.get_running_loop())
        except RuntimeError:
            # Called from outside an event loop — should not happen on the
            # hot path, but build a one-off client rather than crashing.
            return self._build_client()
        client = self._clients_by_loop_id.get(loop_id)
        if client is None:
            client = self._build_client()
            self._clients_by_loop_id[loop_id] = client
        return client

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

        client = self._get_client()
        if client is None:
            logger.warning("SGP is disabled, skipping span upsert")
            return

        sgp_spans = [_build_sgp_span(span, self.env_vars) for span in spans]
        await client.spans.upsert_batch(items=[s.to_request_params() for s in sgp_spans])

    @override
    async def on_spans_end(self, spans: list[Span]) -> None:
        if not spans:
            return

        client = self._get_client()
        if client is None:
            return

        sgp_spans: list[SGPSpan] = []
        for span in spans:
            sgp_span = _build_sgp_span(span, self.env_vars)
            sgp_span.end_time = span.end_time.isoformat()  # type: ignore[union-attr]
            sgp_spans.append(sgp_span)
        await client.spans.upsert_batch(items=[s.to_request_params() for s in sgp_spans])

    @override
    async def shutdown(self) -> None:
        pass
