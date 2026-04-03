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

        with patch(f"{MODULE}.EnvironmentVariables", mock_env), \
             patch(f"{MODULE}.SGPClient"), \
             patch(f"{MODULE}.tracing"), \
             patch(f"{MODULE}.flush_queue"), \
             patch(f"{MODULE}.create_span", mock_create_span):
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

        with patch(f"{MODULE}.EnvironmentVariables", mock_env), \
             patch(f"{MODULE}.create_span", mock_create_span), \
             patch(f"{MODULE}.AsyncSGPClient", return_value=mock_async_client):
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
