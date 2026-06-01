from __future__ import annotations

import uuid
import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from agentex.types.span import Span
from agentex.lib.types.tracing import SGPTracingProcessorConfig

MODULE = "agentex.lib.core.tracing.processors.sgp_tracing_processor"


def _make_config() -> SGPTracingProcessorConfig:
    return SGPTracingProcessorConfig(
        sgp_api_key="test-key",
        sgp_account_id="test-account",
    )


def _make_span(span_id: str | None = None) -> Span:
    return Span(
        id=span_id or str(uuid.uuid4()),
        name="test-span",
        start_time=datetime.now(UTC),
        trace_id="trace-1",
    )


def _make_mock_sgp_span() -> MagicMock:
    sgp_span = MagicMock()
    sgp_span.to_request_params.return_value = {"mock": "params"}
    sgp_span.start_time = None
    sgp_span.end_time = None
    sgp_span.output = None
    sgp_span.metadata = None
    return sgp_span


# ---------------------------------------------------------------------------
# Sync processor tests
# ---------------------------------------------------------------------------


class TestSGPSyncTracingProcessor:
    @staticmethod
    def _make_processor():
        mock_env = MagicMock()
        mock_env.refresh.return_value = MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)
        mock_create_span = MagicMock(side_effect=lambda **kwargs: _make_mock_sgp_span())

        with patch(f"{MODULE}.EnvironmentVariables", mock_env), patch(f"{MODULE}.SGPClient"), patch(
            f"{MODULE}.tracing"
        ), patch(f"{MODULE}.flush_queue"), patch(f"{MODULE}.create_span", mock_create_span):
            from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
                SGPSyncTracingProcessor,
            )

            processor = SGPSyncTracingProcessor(_make_config())

        return processor, mock_create_span

    def test_processor_holds_no_per_span_state(self):
        """Stateless processor must not retain any per-span dict between lifecycle events."""
        processor, _ = self._make_processor()
        assert not hasattr(processor, "_spans")

    def test_span_lifecycle_produces_two_flushes(self):
        """Each span produces one flush on start and one on end."""
        processor, _ = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()) as mock_cs:
            for _ in range(100):
                span = _make_span()
                processor.on_span_start(span)
                span.end_time = datetime.now(UTC)
                processor.on_span_end(span)

        # 100 spans × (1 start + 1 end) = 200 build calls.
        assert mock_cs.call_count == 200

    def test_span_end_without_prior_start_still_flushes(self):
        """Cross-pod Temporal case: END activity lands on a pod that never saw START.

        Today this used to be a silent no-op. After the stateless refactor it
        must still flush a complete span (start_time + end_time + payload).
        """
        processor, _ = self._make_processor()

        captured_spans: list[MagicMock] = []

        def capture_create_span(**kwargs):
            sgp_span = _make_mock_sgp_span()
            captured_spans.append(sgp_span)
            return sgp_span

        with patch(f"{MODULE}.create_span", side_effect=capture_create_span):
            span = _make_span()
            span.end_time = datetime.now(UTC)
            # No on_span_start — END lands here for the first time.
            processor.on_span_end(span)

        assert len(captured_spans) == 1
        assert captured_spans[0].flush.called
        assert captured_spans[0].start_time is not None
        assert captured_spans[0].end_time is not None


# ---------------------------------------------------------------------------
# Async processor tests
# ---------------------------------------------------------------------------


class TestSGPAsyncTracingProcessor:
    @staticmethod
    def _make_processor():
        mock_env = MagicMock()
        mock_env.refresh.return_value = MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)
        mock_create_span = MagicMock(side_effect=lambda **kwargs: _make_mock_sgp_span())

        mock_async_client = MagicMock()
        mock_async_client.spans.upsert_batch = AsyncMock()

        with patch(f"{MODULE}.EnvironmentVariables", mock_env), patch(f"{MODULE}.create_span", mock_create_span), patch(
            f"{MODULE}.AsyncSGPClient", return_value=mock_async_client
        ):
            from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
                SGPAsyncTracingProcessor,
            )

            processor = SGPAsyncTracingProcessor(_make_config())

        # Force the per-loop cache to return the mock for whatever loop the
        # test runs on, by stubbing _get_client directly.
        processor._get_client = lambda: mock_async_client  # type: ignore[method-assign]

        return processor, mock_create_span, mock_async_client

    def test_processor_holds_no_per_span_state(self):
        """Stateless processor must not retain any per-span dict between lifecycle events."""
        processor, _, _ = self._make_processor()
        assert not hasattr(processor, "_spans")

    async def test_span_lifecycle_produces_two_upserts(self):
        """Each span produces one upsert_batch call on start and one on end."""
        processor, _, mock_client = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            span = _make_span()
            await processor.on_span_start(span)
            span.end_time = datetime.now(UTC)
            await processor.on_span_end(span)

        assert mock_client.spans.upsert_batch.call_count == 2

    async def test_span_end_without_prior_start_still_upserts(self):
        """Cross-pod Temporal case: END activity lands on a pod that never saw START.

        Today this used to be a silent no-op. After the stateless refactor it
        must still upsert a complete span via upsert_batch.
        """
        processor, _, mock_client = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            span = _make_span()
            span.end_time = datetime.now(UTC)
            # No on_span_start — END lands here for the first time.
            await processor.on_span_end(span)

        assert mock_client.spans.upsert_batch.call_count == 1
        items = mock_client.spans.upsert_batch.call_args.kwargs["items"]
        assert len(items) == 1

    async def test_sgp_span_input_and_output_propagated_on_end(self):
        """on_span_end should send the span's current input and output via upsert_batch."""
        processor, _, mock_client = self._make_processor()

        captured: list[MagicMock] = []

        def capture_create_span(**kwargs):
            sgp_span = _make_mock_sgp_span()
            captured.append(sgp_span)
            return sgp_span

        mock_create_span = MagicMock(side_effect=capture_create_span)
        with patch(f"{MODULE}.create_span", mock_create_span):
            span = _make_span()
            span.input = {"messages": [{"role": "user", "content": "hello"}]}
            await processor.on_span_start(span)

            span.input = {
                "messages": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "hi"},
                ]
            }
            span.output = {"response": "hi"}
            span.end_time = datetime.now(UTC)
            await processor.on_span_end(span)

        assert mock_client.spans.upsert_batch.call_count == 2  # start + end
        # The end-time SGPSpan should have end_time populated.
        end_span = captured[-1]
        assert end_span.end_time is not None
        # Verify the updated input/output reached create_span on the end call.
        end_call_kwargs = mock_create_span.call_args_list[-1].kwargs
        assert end_call_kwargs["input"]["messages"][-1]["role"] == "assistant"
        assert end_call_kwargs["output"] == {"response": "hi"}

    async def test_on_spans_start_sends_single_upsert_for_batch(self):
        """Given N spans at once, on_spans_start should make ONE upsert_batch HTTP call."""
        processor, _, mock_client = self._make_processor()

        n = 10
        spans = [_make_span() for _ in range(n)]
        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            await processor.on_spans_start(spans)

        assert mock_client.spans.upsert_batch.call_count == 1, (
            "Batched on_spans_start must make exactly one upsert_batch HTTP call"
        )
        items = mock_client.spans.upsert_batch.call_args.kwargs["items"]
        assert len(items) == n

    async def test_on_spans_start_records_export_success_metrics(self, monkeypatch):
        monkeypatch.setenv("AGENTEX_TRACING_METRICS", "1")
        import agentex.lib.core.observability.tracing_metrics_recording as recording

        recording._metrics_enabled = None
        recording._tracing = None
        processor, _, mock_client = self._make_processor()
        mock_metrics = MagicMock()

        n = 4
        spans = [_make_span() for _ in range(n)]
        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()), patch(
            "agentex.lib.core.observability.tracing_metrics.get_tracing_metrics",
            return_value=mock_metrics,
        ):
            await processor.on_spans_start(spans)

        mock_metrics.export_batches.add.assert_called_once_with(
            1,
            {"processor": "sgp", "event_type": "start"},
        )
        mock_metrics.export_spans.add.assert_called_once_with(
            n,
            {"processor": "sgp", "event_type": "start"},
        )
        assert mock_client.spans.upsert_batch.call_count == 1

    async def test_get_client_caches_per_event_loop(self):
        """The processor must keep one client per event loop, and reuse it
        across calls within the same loop.  This is what enables connection
        keepalive instead of paying a TLS handshake per span.
        """
        mock_env = MagicMock()
        mock_env.refresh.return_value = MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)

        with patch(f"{MODULE}.EnvironmentVariables", mock_env), patch(
            f"{MODULE}.AsyncSGPClient"
        ) as mock_sgp_cls:
            mock_sgp_cls.side_effect = lambda **kwargs: MagicMock()

            from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
                SGPAsyncTracingProcessor,
            )

            processor = SGPAsyncTracingProcessor(_make_config())

            # Construction should NOT eagerly build the client (no running
            # loop guarantee at import time).
            assert mock_sgp_cls.call_count == 0

            c1 = processor._get_client()
            c2 = processor._get_client()
            c3 = processor._get_client()

            # First call builds the client; subsequent calls in the same
            # loop return the cached one.
            assert mock_sgp_cls.call_count == 1, (
                f"Expected client to be built once per loop, but AsyncSGPClient "
                f"was called {mock_sgp_cls.call_count} times"
            )
            assert c1 is c2 is c3

    async def test_get_client_keepalive_is_enabled(self):
        """Regression guard: the per-loop client must use keepalive (the whole
        point of the per-loop cache).  Verify max_keepalive_connections > 0.
        """
        import httpx as _httpx

        captured_limits: list[_httpx.Limits] = []

        original_async_client = _httpx.AsyncClient

        def capture_limits(*args, **kwargs):
            limits = kwargs.get("limits")
            if limits is not None:
                captured_limits.append(limits)
            return original_async_client(*args, **kwargs)

        mock_env = MagicMock()
        mock_env.refresh.return_value = MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)

        with patch(f"{MODULE}.EnvironmentVariables", mock_env), patch(
            f"{MODULE}.AsyncSGPClient"
        ), patch("httpx.AsyncClient", side_effect=capture_limits):
            from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
                SGPAsyncTracingProcessor,
            )

            processor = SGPAsyncTracingProcessor(_make_config())
            processor._get_client()

        assert len(captured_limits) == 1
        max_keepalive = captured_limits[0].max_keepalive_connections
        assert max_keepalive is not None and max_keepalive > 0, (
            f"SGP async client should have keepalive enabled, got "
            f"max_keepalive_connections={max_keepalive}"
        )

    def test_cache_is_weakkeydict_and_evicts_dead_loops(self):
        """Regression guard for the id()-reuse bug: the per-loop cache must
        be a WeakKeyDictionary so a GC'd loop's entry is evicted.  Otherwise
        a new loop landing at the same memory address would reuse the dead
        loop's client, reintroducing the "bound to a different event loop"
        error the per-loop cache was built to prevent.
        """
        import gc
        import weakref

        mock_env = MagicMock()
        mock_env.refresh.return_value = MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)

        with patch(f"{MODULE}.EnvironmentVariables", mock_env), patch(f"{MODULE}.AsyncSGPClient"):
            from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
                SGPAsyncTracingProcessor,
            )

            processor = SGPAsyncTracingProcessor(_make_config())

        # Storage type itself: WeakKeyDictionary, not plain dict.
        assert isinstance(processor._clients_by_loop, weakref.WeakKeyDictionary)

        # End-to-end check: insert under a loop, drop the loop, the entry
        # must vanish after GC.
        loop = asyncio.new_event_loop()
        try:
            processor._clients_by_loop[loop] = MagicMock()
            assert len(processor._clients_by_loop) == 1
        finally:
            loop.close()
        del loop
        gc.collect()
        assert len(processor._clients_by_loop) == 0, (
            "WeakKeyDictionary should have evicted the dead loop's entry; "
            "remaining keys would cause stale-client reuse on id() recycling."
        )

    async def test_disabled_processor_returns_none_client(self):
        """When config is missing api_key/account_id, _get_client must return
        None and no HTTP client must be constructed."""
        from agentex.lib.types.tracing import SGPTracingProcessorConfig

        mock_env = MagicMock()
        mock_env.refresh.return_value = MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)

        with patch(f"{MODULE}.EnvironmentVariables", mock_env), patch(
            f"{MODULE}.AsyncSGPClient"
        ) as mock_sgp_cls:
            from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
                SGPAsyncTracingProcessor,
            )

            processor = SGPAsyncTracingProcessor(
                SGPTracingProcessorConfig(sgp_api_key="", sgp_account_id="")
            )

            assert processor._get_client() is None
            assert mock_sgp_cls.call_count == 0

    async def test_on_spans_end_sends_single_upsert_for_batch(self):
        """Given N spans at once, on_spans_end should make ONE upsert_batch HTTP call."""
        processor, _, mock_client = self._make_processor()

        n = 10
        spans = [_make_span() for _ in range(n)]
        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            await processor.on_spans_start(spans)

        mock_client.spans.upsert_batch.reset_mock()

        for span in spans:
            span.end_time = datetime.now(UTC)
        await processor.on_spans_end(spans)

        assert mock_client.spans.upsert_batch.call_count == 1, (
            "Batched on_spans_end must make exactly one upsert_batch HTTP call"
        )
        items = mock_client.spans.upsert_batch.call_args.kwargs["items"]
        assert len(items) == n
