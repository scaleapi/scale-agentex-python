from __future__ import annotations

import uuid
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


class TestSGPSyncTracingProcessorMemoryLeak:
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

    def test_spans_not_leaked_after_completed_lifecycle(self):
        processor, _ = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            for _ in range(100):
                span = _make_span()
                processor.on_span_start(span)
                span.end_time = datetime.now(UTC)
                processor.on_span_end(span)

        assert len(processor._spans) == 0, (
            f"Expected 0 spans after 100 complete lifecycles, got {len(processor._spans)} — memory leak!"
        )

    def test_spans_present_during_active_lifecycle(self):
        processor, _ = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            span = _make_span()
            processor.on_span_start(span)
            assert len(processor._spans) == 1, "Span should be tracked while active"

            span.end_time = datetime.now(UTC)
            processor.on_span_end(span)
            assert len(processor._spans) == 0, "Span should be removed after end"

    def test_span_end_for_unknown_span_is_noop(self):
        processor, _ = self._make_processor()

        span = _make_span()
        # End a span that was never started — should not raise
        span.end_time = datetime.now(UTC)
        processor.on_span_end(span)

        assert len(processor._spans) == 0


# ---------------------------------------------------------------------------
# Async processor tests
# ---------------------------------------------------------------------------


class TestSGPAsyncTracingProcessorMemoryLeak:
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

        # Wire up the mock client after construction (constructor stores it)
        processor.sgp_async_client = mock_async_client

        # Keep create_span mock active for on_span_start calls
        return processor, mock_create_span

    async def test_spans_not_leaked_after_completed_lifecycle(self):
        processor, _ = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            for _ in range(100):
                span = _make_span()
                await processor.on_span_start(span)
                span.end_time = datetime.now(UTC)
                await processor.on_span_end(span)

        assert len(processor._spans) == 0, (
            f"Expected 0 spans after 100 complete lifecycles, got {len(processor._spans)} — memory leak!"
        )

    async def test_spans_present_during_active_lifecycle(self):
        processor, _ = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            span = _make_span()
            await processor.on_span_start(span)
            assert len(processor._spans) == 1, "Span should be tracked while active"

            span.end_time = datetime.now(UTC)
            await processor.on_span_end(span)
            assert len(processor._spans) == 0, "Span should be removed after end"

    async def test_span_end_for_unknown_span_is_noop(self):
        processor, _ = self._make_processor()

        span = _make_span()
        span.end_time = datetime.now(UTC)
        await processor.on_span_end(span)

        assert len(processor._spans) == 0


# ---------------------------------------------------------------------------
# Async processor batching tests (regression for OVE-2)
#
# Previously, on_span_start and on_span_end each issued an awaited
# upsert_batch(items=[one]) call on the agent's hot path with HTTP keepalive
# disabled. The processor now buffers events and flushes them in batches
# from a background asyncio.Task, mirroring the SDK's TraceQueueManager.
# ---------------------------------------------------------------------------


class TestSGPAsyncTracingProcessorBatching:
    @staticmethod
    def _make_processor():
        mock_env = MagicMock()
        mock_env.refresh.return_value = MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)

        mock_async_client = MagicMock()
        mock_async_client.spans.upsert_batch = AsyncMock()

        with patch(f"{MODULE}.EnvironmentVariables", mock_env), patch(
            f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()
        ), patch(f"{MODULE}.AsyncSGPClient", return_value=mock_async_client):
            from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
                SGPAsyncTracingProcessor,
            )

            processor = SGPAsyncTracingProcessor(_make_config())

        processor.sgp_async_client = mock_async_client
        return processor, mock_async_client

    async def test_span_event_does_not_trigger_immediate_upsert(self):
        """Regression: a single span event must not result in an upsert call
        on the hot path. Events must be enqueued and flushed by the worker."""
        processor, client = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            span = _make_span()
            await processor.on_span_start(span)

        assert client.spans.upsert_batch.call_count == 0, "on_span_start should enqueue, not trigger a network call"

    async def test_shutdown_flushes_queued_spans_in_one_batch(self):
        """Many span events should be coalesced into a single upsert_batch
        call when the buffer fits under MAX_BATCH_SIZE (50)."""
        processor, client = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            for _ in range(5):
                span = _make_span()
                await processor.on_span_start(span)
                span.end_time = datetime.now(UTC)
                await processor.on_span_end(span)

        await processor.shutdown()

        assert client.spans.upsert_batch.call_count == 1, (
            f"Expected a single batched upsert, got {client.spans.upsert_batch.call_count}"
        )
        items = client.spans.upsert_batch.call_args.kwargs["items"]
        # 5 starts + 5 ends = 10 enqueued items, well under MAX_BATCH_SIZE.
        assert len(items) == 10, f"Expected 10 items in the batch, got {len(items)}"

    async def test_owned_client_recreated_after_loop_swap(self):
        """When the running loop changes (sync-ACP / per-request loops),
        the processor's owned client must be recreated so it isn't bound to
        a dead loop. This is the reason the original implementation disabled
        keepalive — re-creating the client on the new loop lets us keep
        keepalive on instead.
        """
        env_mock = MagicMock(refresh=MagicMock(return_value=MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)))
        with patch(f"{MODULE}.EnvironmentVariables", env_mock), patch(
            f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()
        ), patch(f"{MODULE}.AsyncSGPClient") as mock_client_cls:
            first = MagicMock(spans=MagicMock(upsert_batch=AsyncMock()))
            second = MagicMock(spans=MagicMock(upsert_batch=AsyncMock()))
            mock_client_cls.side_effect = [first, second]

            from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
                SGPAsyncTracingProcessor,
            )

            processor = SGPAsyncTracingProcessor(_make_config())

            await processor.on_span_start(_make_span())
            assert processor.sgp_async_client is first
            assert mock_client_cls.call_count == 1

            # Simulate a loop swap: processor's tracked loop is stale and
            # the worker is gone. Re-initialization must recreate the
            # owned client (since `_client_owned_at_loop` no longer matches
            # the running loop).
            stale_loop = MagicMock()
            processor._loop = stale_loop
            processor._client_owned_at_loop = stale_loop
            processor._worker = None

            await processor.on_span_start(_make_span())
            assert processor.sgp_async_client is second, "Owned client must be recreated after loop swap"
            assert mock_client_cls.call_count == 2

            await processor.shutdown()

    async def test_injected_client_preserved_across_reinit(self):
        """A client assigned externally (e.g. a test mock or a caller-built
        client) must not be replaced by the processor, even on simulated
        loop swaps."""
        processor, original_client = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            await processor.on_span_start(_make_span())
        assert processor.sgp_async_client is original_client

        # Simulate a loop swap. Because the client was injected
        # (`_client_owned_at_loop` stays None), it must be preserved.
        processor._loop = MagicMock()
        processor._worker = None

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            await processor.on_span_start(_make_span())
        assert processor.sgp_async_client is original_client, "Injected client must not be replaced"

        await processor.shutdown()

    async def test_async_client_constructed_without_disabling_keepalive(self):
        """Regression: the previous implementation built AsyncSGPClient with
        httpx.Limits(max_keepalive_connections=0) to dodge cross-loop errors,
        paying a TCP+TLS handshake on every span event. The lazy-init pattern
        binds the client to the running loop, so keepalive can stay on."""
        with patch(
            f"{MODULE}.EnvironmentVariables",
            MagicMock(refresh=MagicMock(return_value=MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None))),
        ), patch(f"{MODULE}.AsyncSGPClient") as mock_client_cls:
            from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
                SGPAsyncTracingProcessor,
            )

            processor = SGPAsyncTracingProcessor(_make_config())

            with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
                await processor.on_span_start(_make_span())

            mock_client_cls.assert_called_once()
            kwargs = mock_client_cls.call_args.kwargs
            # The fix: do not pass an http_client overriding keepalive.
            assert "http_client" not in kwargs, (
                "AsyncSGPClient should not receive a custom http_client that disables keepalive"
            )
            # Cleanup: cancel the worker so we don't leak a task across tests.
            await processor.shutdown()
