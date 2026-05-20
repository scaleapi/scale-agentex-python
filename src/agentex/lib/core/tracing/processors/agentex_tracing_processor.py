import asyncio
from typing import TYPE_CHECKING, Any, Dict, override

from agentex import Agentex
from agentex.types.span import Span
from agentex.lib.types.tracing import AgentexTracingProcessorConfig
from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.tracing.processors.tracing_processor_interface import (
    SyncTracingProcessor,
    AsyncTracingProcessor,
)

if TYPE_CHECKING:
    from agentex import AsyncAgentex


class AgentexSyncTracingProcessor(SyncTracingProcessor):
    def __init__(self, config: AgentexTracingProcessorConfig):  # noqa: ARG002
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
            task_id=span.task_id,
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
    def __init__(self, config: AgentexTracingProcessorConfig):  # noqa: ARG002
        # Per-event-loop client cache.  httpx.AsyncClient is bound to the
        # loop that created it, so in sync-ACP / streaming contexts (where
        # the active loop can change between requests) we keep one client
        # per loop instead of disabling keepalive entirely.
        self._clients_by_loop_id: dict[int, "AsyncAgentex"] = {}

    def _build_client(self) -> "AsyncAgentex":
        import httpx

        # Keepalive ON: connections are reused within a single event loop,
        # eliminating the TLS-handshake-per-span penalty under load.
        return create_async_agentex_client(
            http_client=httpx.AsyncClient(
                limits=httpx.Limits(max_keepalive_connections=20),
            ),
        )

    @property
    def client(self) -> "AsyncAgentex":
        try:
            loop_id = id(asyncio.get_running_loop())
        except RuntimeError:
            return self._build_client()
        client = self._clients_by_loop_id.get(loop_id)
        if client is None:
            client = self._build_client()
            self._clients_by_loop_id[loop_id] = client
        return client

    # TODO(AGX1-199): Add batch create/update endpoints to Agentex API and use
    # them here instead of one HTTP call per span.
    # https://linear.app/scale-epd/issue/AGX1-199/add-agentex-batch-endpoint-for-traces
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
            task_id=span.task_id,
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
