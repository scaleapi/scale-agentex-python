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

        # Wire up the mock client after construction. The processor lazy-inits
        # its own client on first async call; pre-setting it bypasses that path.
        processor.sgp_async_client = mock_async_client
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
# Async client lifecycle tests
#
# These cover the lazy / per-loop client construction and the dropped
# `max_keepalive_connections=0` workaround (PR A of the OVE-2 split).
# ---------------------------------------------------------------------------


class TestSGPAsyncTracingProcessorClientLifecycle:
    async def test_client_constructed_without_disabling_keepalive(self):
        """The previous implementation built `AsyncSGPClient` with
        `httpx.Limits(max_keepalive_connections=0)` to dodge cross-loop
        errors, paying a TCP+TLS handshake on every span event. The lazy
        per-loop pattern lets keepalive stay on."""
        env_mock = MagicMock(refresh=MagicMock(return_value=MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)))
        with patch(f"{MODULE}.EnvironmentVariables", env_mock), patch(
            f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()
        ), patch(f"{MODULE}.AsyncSGPClient") as mock_client_cls:
            mock_client_cls.return_value = MagicMock(spans=MagicMock(upsert_batch=AsyncMock()))

            from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
                SGPAsyncTracingProcessor,
            )

            processor = SGPAsyncTracingProcessor(_make_config())
            await processor.on_span_start(_make_span())

            mock_client_cls.assert_called_once()
            kwargs = mock_client_cls.call_args.kwargs
            assert "http_client" not in kwargs, (
                "AsyncSGPClient must not receive a custom http_client that disables keepalive"
            )

    async def test_owned_client_recreated_after_loop_swap(self):
        """When the running loop changes (sync-ACP / per-request loops),
        the processor's owned client must be recreated so it isn't bound to
        a dead loop. This is what lets us drop the keepalive workaround."""
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

            # Simulate a loop swap: the processor's tracked loop is stale.
            # The next call must recreate the client.
            processor._client_owned_at_loop = MagicMock()

            await processor.on_span_start(_make_span())
            assert processor.sgp_async_client is second, "Owned client must be recreated after loop swap"
            assert mock_client_cls.call_count == 2

    async def test_injected_client_preserved(self):
        """A client assigned externally (test mock or caller-built) must
        never be replaced by the processor. Contract:
        `_client_owned_at_loop=None` marks externally-managed clients and
        skips both the create-on-None branch and the replace-on-loop-change
        branch, so the injected client is preserved across any number of
        calls."""
        env_mock = MagicMock(refresh=MagicMock(return_value=MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)))
        injected = MagicMock(spans=MagicMock(upsert_batch=AsyncMock()))

        with patch(f"{MODULE}.EnvironmentVariables", env_mock), patch(
            f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()
        ), patch(f"{MODULE}.AsyncSGPClient") as mock_client_cls:
            from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
                SGPAsyncTracingProcessor,
            )

            processor = SGPAsyncTracingProcessor(_make_config())
            processor.sgp_async_client = injected

            for _ in range(3):
                await processor.on_span_start(_make_span())

            assert processor.sgp_async_client is injected
            assert mock_client_cls.call_count == 0, (
                "Injected client must not be replaced (no AsyncSGPClient construction)"
            )
