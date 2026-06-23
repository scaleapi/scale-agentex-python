import os
import asyncio
import weakref
from typing import TYPE_CHECKING, Any, Dict, override

from agentex import Agentex
from agentex.types.span import Span
from agentex.lib.types.tracing import AgentexTracingProcessorConfig
from agentex.lib.utils.logging import make_logger
from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.core.tracing.processors.tracing_processor_interface import (
    SyncTracingProcessor,
    AsyncTracingProcessor,
)

if TYPE_CHECKING:
    from agentex import AsyncAgentex

logger = make_logger(__name__)


# NOTE: This is the Agentex-backend toggle (writes to the agentex `spans`
# table via the Agentex API). It is intentionally SEPARATE from the SGP/EGP
# processor's ``AGENTEX_TRACING_SKIP_SPAN_START`` so the two backends can be
# controlled independently.
_SKIP_SPAN_START_ENV = "AGENTEX_TRACING_SKIP_AGENTEX_SPAN_START"


def _skip_span_start_enabled() -> bool:
    """Whether to skip the Agentex span-start write and persist each span only on end.

    The Agentex processor otherwise writes every span twice: a ``spans.create``
    on start (no ``end_time``/``output`` yet) and a ``spans.update`` on end.
    The start row is overwritten by the end write moments later, so persisting
    it doubles the per-span HTTP/DB write volume against the Agentex control
    plane — the load that timed out span-start activities and pressured the
    Agentex Postgres connection pool under load.

    When enabled (the default), the start write is skipped and the END write
    becomes a single ``spans.create`` carrying the complete span — one INSERT
    per span instead of an INSERT + UPDATE. (A plain ``spans.update`` on end
    would 404 because the row was never created.)

    Default ON. Set ``AGENTEX_TRACING_SKIP_AGENTEX_SPAN_START`` to
    ``0``/``false``/``no``/``off`` to restore the start write — e.g. if you
    need in-flight spans visible before they complete, or spans that never end
    (process crash) to still be persisted.
    """
    raw = os.environ.get(_SKIP_SPAN_START_ENV, "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _create_kwargs(span: Span) -> Dict[str, Any]:
    """Full-span kwargs for ``spans.create`` — used on start (skip disabled) and
    on end (skip enabled, single-INSERT path)."""
    return {
        "name": span.name,
        "start_time": span.start_time,
        "end_time": span.end_time,
        "id": span.id,
        "trace_id": span.trace_id,
        "parent_id": span.parent_id,
        "input": span.input,
        "output": span.output,
        "data": span.data,
        "task_id": span.task_id,
    }


class AgentexSyncTracingProcessor(SyncTracingProcessor):
    def __init__(self, config: AgentexTracingProcessorConfig):  # noqa: ARG002
        self.client = Agentex()
        logger.info(
            "Agentex tracing span-start write %s (%s)",
            "disabled — end-only ingest" if _skip_span_start_enabled() else "enabled",
            _SKIP_SPAN_START_ENV,
        )

    @override
    def on_span_start(self, span: Span) -> None:
        # End-only ingest: by default the start write is skipped (see
        # _skip_span_start_enabled) so each span is persisted once, on end.
        if _skip_span_start_enabled():
            return
        self.client.spans.create(**_create_kwargs(span))

    @override
    def on_span_end(self, span: Span) -> None:
        # End-only ingest: the start create was skipped, so persist the complete
        # span as a single INSERT here (a bare spans.update would 404 — no row).
        if _skip_span_start_enabled():
            self.client.spans.create(**_create_kwargs(span))
            return

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
        # per loop instead of disabling keepalive entirely.  The cache is a
        # WeakKeyDictionary so a GC'd loop and its client are evicted
        # automatically — using id() as a key would reuse entries when
        # CPython recycles a freed loop's memory address.
        self._clients_by_loop: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, "AsyncAgentex"
        ] = weakref.WeakKeyDictionary()
        logger.info(
            "Agentex tracing span-start write %s (%s)",
            "disabled — end-only ingest" if _skip_span_start_enabled() else "enabled",
            _SKIP_SPAN_START_ENV,
        )

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
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return self._build_client()
        client = self._clients_by_loop.get(loop)
        if client is None:
            client = self._build_client()
            self._clients_by_loop[loop] = client
        return client

    # TODO(AGX1-199): Add batch create/update endpoints to Agentex API and use
    # them here instead of one HTTP call per span.
    # https://linear.app/scale-epd/issue/AGX1-199/add-agentex-batch-endpoint-for-traces
    @override
    async def on_span_start(self, span: Span) -> None:
        # End-only ingest: by default the start write is skipped (see
        # _skip_span_start_enabled) so each span is persisted once, on end.
        if _skip_span_start_enabled():
            return
        await self.client.spans.create(**_create_kwargs(span))

    @override
    async def on_span_end(self, span: Span) -> None:
        # End-only ingest: the start create was skipped, so persist the complete
        # span as a single INSERT here (a bare spans.update would 404 — no row).
        if _skip_span_start_enabled():
            await self.client.spans.create(**_create_kwargs(span))
            return

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
