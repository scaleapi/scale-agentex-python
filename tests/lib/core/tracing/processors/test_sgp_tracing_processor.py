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

        # Wire up the mock client after construction (constructor stores it)
        processor.sgp_async_client = mock_async_client

        return processor, mock_create_span

    def test_processor_holds_no_per_span_state(self):
        """Stateless processor must not retain any per-span dict between lifecycle events."""
        processor, _ = self._make_processor()
        assert not hasattr(processor, "_spans")

    async def test_span_lifecycle_produces_two_upserts(self):
        """Each span produces one upsert_batch call on start and one on end."""
        processor, _ = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            span = _make_span()
            await processor.on_span_start(span)
            span.end_time = datetime.now(UTC)
            await processor.on_span_end(span)

        assert processor.sgp_async_client.spans.upsert_batch.call_count == 2

    async def test_span_end_without_prior_start_still_upserts(self):
        """Cross-pod Temporal case: END activity lands on a pod that never saw START.

        Today this used to be a silent no-op. After the stateless refactor it
        must still upsert a complete span via upsert_batch.
        """
        processor, _ = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            span = _make_span()
            span.end_time = datetime.now(UTC)
            # No on_span_start — END lands here for the first time.
            await processor.on_span_end(span)

        assert processor.sgp_async_client.spans.upsert_batch.call_count == 1
        items = processor.sgp_async_client.spans.upsert_batch.call_args.kwargs["items"]
        assert len(items) == 1

    async def test_sgp_span_input_and_output_propagated_on_end(self):
        """on_span_end should send the span's current input and output via upsert_batch."""
        processor, _ = self._make_processor()

        captured: list[MagicMock] = []

        def capture_create_span(**kwargs):
            sgp_span = _make_mock_sgp_span()
            captured.append(sgp_span)
            return sgp_span

        with patch(f"{MODULE}.create_span", side_effect=capture_create_span):
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

        assert processor.sgp_async_client.spans.upsert_batch.call_count == 2  # start + end
        # The end-time SGPSpan should have end_time populated.
        end_span = captured[-1]
        assert end_span.end_time is not None

    async def test_on_spans_start_sends_single_upsert_for_batch(self):
        """Given N spans at once, on_spans_start should make ONE upsert_batch HTTP call."""
        processor, _ = self._make_processor()

        n = 10
        spans = [_make_span() for _ in range(n)]
        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            await processor.on_spans_start(spans)

        assert processor.sgp_async_client.spans.upsert_batch.call_count == 1, (
            "Batched on_spans_start must make exactly one upsert_batch HTTP call"
        )
        items = processor.sgp_async_client.spans.upsert_batch.call_args.kwargs["items"]
        assert len(items) == n

    async def test_on_spans_end_sends_single_upsert_for_batch(self):
        """Given N spans at once, on_spans_end should make ONE upsert_batch HTTP call."""
        processor, _ = self._make_processor()

        n = 10
        spans = [_make_span() for _ in range(n)]
        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            await processor.on_spans_start(spans)

        processor.sgp_async_client.spans.upsert_batch.reset_mock()

        for span in spans:
            span.end_time = datetime.now(UTC)
        await processor.on_spans_end(spans)

        assert processor.sgp_async_client.spans.upsert_batch.call_count == 1, (
            "Batched on_spans_end must make exactly one upsert_batch HTTP call"
        )
        items = processor.sgp_async_client.spans.upsert_batch.call_args.kwargs["items"]
        assert len(items) == n
