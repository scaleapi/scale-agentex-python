from __future__ import annotations

import uuid
import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

    def test_span_lifecycle_produces_two_flushes(self, monkeypatch):
        """With start writes enabled, each span produces one flush on start and one on end."""
        monkeypatch.setenv("AGENTEX_TRACING_SKIP_SPAN_START", "0")
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

    def test_span_start_skipped_by_default(self, monkeypatch):
        """Default (end-only): on_span_start is a no-op; only on_span_end writes."""
        monkeypatch.delenv("AGENTEX_TRACING_SKIP_SPAN_START", raising=False)
        processor, _ = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()) as mock_cs:
            span = _make_span()
            processor.on_span_start(span)
            assert mock_cs.call_count == 0  # start skipped — nothing built or flushed
            span.end_time = datetime.now(UTC)
            processor.on_span_end(span)

        assert mock_cs.call_count == 1  # only the end write

    def test_span_start_emitted_when_skip_disabled(self, monkeypatch):
        """With skip disabled, on_span_start builds and flushes a span."""
        monkeypatch.setenv("AGENTEX_TRACING_SKIP_SPAN_START", "0")
        processor, _ = self._make_processor()

        captured: list[MagicMock] = []

        def capture(**kwargs):
            sgp_span = _make_mock_sgp_span()
            captured.append(sgp_span)
            return sgp_span

        with patch(f"{MODULE}.create_span", side_effect=capture):
            processor.on_span_start(_make_span())

        assert len(captured) == 1
        assert captured[0].flush.called


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

    async def test_span_lifecycle_produces_two_upserts(self, monkeypatch):
        """With start writes enabled, each span produces one upsert on start and one on end."""
        monkeypatch.setenv("AGENTEX_TRACING_SKIP_SPAN_START", "0")
        processor, _, mock_client = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            span = _make_span()
            await processor.on_span_start(span)
            span.end_time = datetime.now(UTC)
            await processor.on_span_end(span)

        assert mock_client.spans.upsert_batch.call_count == 2

    async def test_spans_start_skipped_by_default(self, monkeypatch):
        """Default (end-only): on_spans_start makes no upsert; on_spans_end does."""
        monkeypatch.delenv("AGENTEX_TRACING_SKIP_SPAN_START", raising=False)
        processor, _, mock_client = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            spans = [_make_span() for _ in range(3)]
            await processor.on_spans_start(spans)
            assert mock_client.spans.upsert_batch.call_count == 0  # start skipped
            for s in spans:
                s.end_time = datetime.now(UTC)
            await processor.on_spans_end(spans)

        assert mock_client.spans.upsert_batch.call_count == 1  # only the end write

    async def test_spans_start_emitted_when_skip_disabled(self, monkeypatch):
        """With skip disabled, on_spans_start makes one upsert_batch call."""
        monkeypatch.setenv("AGENTEX_TRACING_SKIP_SPAN_START", "0")
        processor, _, mock_client = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            await processor.on_spans_start([_make_span()])

        assert mock_client.spans.upsert_batch.call_count == 1

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

    async def test_sgp_span_input_and_output_propagated_on_end(self, monkeypatch):
        """on_span_end should send the span's current input and output via upsert_batch."""
        monkeypatch.setenv("AGENTEX_TRACING_SKIP_SPAN_START", "0")
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

    async def test_on_spans_start_sends_single_upsert_for_batch(self, monkeypatch):
        """Given N spans at once, on_spans_start should make ONE upsert_batch HTTP call."""
        monkeypatch.setenv("AGENTEX_TRACING_SKIP_SPAN_START", "0")
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
        monkeypatch.setenv("AGENTEX_TRACING_SKIP_SPAN_START", "0")
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


# ---------------------------------------------------------------------------
# AGENTEX_TRACING_SKIP_SPAN_START env parsing
# ---------------------------------------------------------------------------


class TestSkipSpanStartEnv:
    @staticmethod
    def _fn():
        from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
            _skip_span_start_enabled,
        )

        return _skip_span_start_enabled

    def test_default_is_skip_enabled(self, monkeypatch):
        """Unset → skip span-start (end-only ingest is the default)."""
        monkeypatch.delenv("AGENTEX_TRACING_SKIP_SPAN_START", raising=False)
        assert self._fn()() is True

    @pytest.mark.parametrize("val", ["0", "false", "no", "off", "FALSE", "Off", " no "])
    def test_falsy_values_restore_span_start(self, monkeypatch, val):
        monkeypatch.setenv("AGENTEX_TRACING_SKIP_SPAN_START", val)
        assert self._fn()() is False

    @pytest.mark.parametrize("val", ["1", "true", "yes", "on", "anything"])
    def test_other_values_keep_skip_enabled(self, monkeypatch, val):
        monkeypatch.setenv("AGENTEX_TRACING_SKIP_SPAN_START", val)
        assert self._fn()() is True


class TestResolveTraceId:
    def _mod(self):
        import agentex.lib.core.tracing.processors.sgp_tracing_processor as m

        return m

    def test_prefers_active_otel_trace_id(self, monkeypatch):
        m = self._mod()
        monkeypatch.setattr(m, "_active_otel_trace_id", lambda: "4bf92f3577b34da6a3ce929d0e0e4736")
        assert m._resolve_trace_id("task-123") == "4bf92f3577b34da6a3ce929d0e0e4736"

    def test_falls_back_to_agentex_id_without_otel(self, monkeypatch):
        m = self._mod()
        monkeypatch.setattr(m, "_active_otel_trace_id", lambda: None)
        assert m._resolve_trace_id("task-123") == "task-123"

    def test_active_otel_trace_id_none_without_span(self):
        pytest.importorskip("opentelemetry")
        assert self._mod()._active_otel_trace_id() is None

    def test_active_otel_trace_id_returns_w3c_hex(self):
        otel_trace = pytest.importorskip("opentelemetry.trace")
        otel_context = pytest.importorskip("opentelemetry.context")

        span_context = otel_trace.SpanContext(
            trace_id=0x4BF92F3577B34DA6A3CE929D0E0E4736,
            span_id=0x00F067AA0BA902B7,
            is_remote=False,
            trace_flags=otel_trace.TraceFlags(otel_trace.TraceFlags.SAMPLED),
        )
        token = otel_context.attach(otel_trace.set_span_in_context(otel_trace.NonRecordingSpan(span_context)))
        try:
            resolved = self._mod()._active_otel_trace_id()
        finally:
            otel_context.detach(token)
        assert resolved == "4bf92f3577b34da6a3ce929d0e0e4736"


class TestBuildSgpSpanTraceId:
    def _build(self, monkeypatch, otel_id):
        import agentex.lib.core.tracing.processors.sgp_tracing_processor as m

        monkeypatch.setattr(m, "_active_otel_trace_id", lambda: otel_id)
        captured = {}
        monkeypatch.setattr(m, "create_span", lambda **kw: captured.update(kw) or _make_mock_sgp_span())
        env = MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)
        span = _make_span()
        m._build_sgp_span(span, env)
        return captured, span

    def test_adopts_otel_trace_id_and_preserves_agentex_id(self, monkeypatch):
        captured, span = self._build(monkeypatch, "4bf92f3577b34da6a3ce929d0e0e4736")
        assert captured["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert span.data["__agentex_trace_id__"] == "trace-1"

    def test_keeps_agentex_trace_id_without_otel(self, monkeypatch):
        captured, span = self._build(monkeypatch, None)
        assert captured["trace_id"] == "trace-1"
        assert span.data["__agentex_trace_id__"] == "trace-1"
