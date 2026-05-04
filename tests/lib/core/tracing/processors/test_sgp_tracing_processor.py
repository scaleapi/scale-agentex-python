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

    async def test_sgp_span_input_updated_on_end(self):
        """on_span_end should mutate the tracked SGP span and enqueue it.
        With batched flushing, the upsert happens once on shutdown, with the
        final state of the span after both start and end have run."""
        processor, _ = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            span = _make_span()
            span.input = {"messages": [{"role": "user", "content": "hello"}]}
            await processor.on_span_start(span)

        assert len(processor._spans) == 1

        # Simulate modified input at end time
        updated_input: dict[str, object] = {
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ]
        }
        span.input = updated_input
        span.output = {"response": "hi"}
        span.end_time = datetime.now(UTC)
        await processor.on_span_end(span)

        # Span should be removed after end
        assert len(processor._spans) == 0

        # No upsert on the hot path; the worker batches and flushes asynchronously.
        assert processor.sgp_async_client.spans.upsert_batch.call_count == 0

        # Shutdown drains the queue and produces a single batched upsert.
        await processor.shutdown()
        assert processor.sgp_async_client.spans.upsert_batch.call_count == 1


# ---------------------------------------------------------------------------
# Async processor batching tests
#
# Before this change, on_span_start and on_span_end each issued an awaited
# upsert_batch(items=[one]) call on the agent's hot path. The processor now
# buffers events and flushes them in batches from a background asyncio.Task,
# mirroring the SDK's TraceQueueManager.
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

    async def test_drain_splits_into_multiple_batches_above_max_batch_size(self):
        """Spans beyond MAX_BATCH_SIZE (50) must be split across multiple
        upsert_batch calls so a single call never exceeds the cap."""
        processor, client = self._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            for _ in range(40):
                span = _make_span()
                await processor.on_span_start(span)
                span.end_time = datetime.now(UTC)
                await processor.on_span_end(span)

        # 40 starts + 40 ends = 80 enqueued items. With MAX_BATCH_SIZE=50,
        # that's at least 2 upsert calls.
        await processor.shutdown()

        assert client.spans.upsert_batch.call_count >= 2, (
            f"Expected ≥2 batched upserts for 80 events, got {client.spans.upsert_batch.call_count}"
        )
        for call in client.spans.upsert_batch.call_args_list:
            items = call.kwargs["items"]
            assert len(items) <= 50, f"Batch of {len(items)} exceeds MAX_BATCH_SIZE=50"
        total_items = sum(len(call.kwargs["items"]) for call in client.spans.upsert_batch.call_args_list)
        assert total_items == 80, f"Expected 80 items across all batches, got {total_items}"

    async def test_worker_continues_after_unexpected_exception_in_one_batch(self):
        """A single upsert raising an unexpected (non-APIError) exception
        must drop that batch and let the worker keep flushing subsequent
        ones. Regression test for the per-iteration try/except in `_run`."""
        processor, client = self._make_processor()

        # First call raises (unexpected exception → batch dropped),
        # subsequent calls succeed.
        client.spans.upsert_batch.side_effect = [RuntimeError("boom"), None]

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            # First flush — will raise inside _upsert_with_retry, batch dropped.
            span_a = _make_span()
            await processor.on_span_start(span_a)
            span_a.end_time = datetime.now(UTC)
            await processor.on_span_end(span_a)
            assert processor._flush_event is not None
            processor._flush_event.set()
            # Yield so the worker runs the failing flush.
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            # Worker must still be alive and able to handle a second batch.
            span_b = _make_span()
            await processor.on_span_start(span_b)
            span_b.end_time = datetime.now(UTC)
            await processor.on_span_end(span_b)

        await processor.shutdown()

        # First call raised, second succeeded → 2 calls total.
        assert client.spans.upsert_batch.call_count == 2, (
            f"Worker should have made a second upsert attempt after the first failed; "
            f"got {client.spans.upsert_batch.call_count}"
        )


# ---------------------------------------------------------------------------
# Edge-case correctness tests
# ---------------------------------------------------------------------------


class TestSGPAsyncTracingProcessorEdgeCases:
    async def test_disabled_processor_never_enqueues_or_calls_upsert(self):
        """When the config has no api_key / account_id, the processor must
        be a no-op: no client constructed, no worker spun up, no upsert
        calls. Only span tracking in `_spans` is preserved (matches the
        sync processor's contract)."""
        env_mock = MagicMock(refresh=MagicMock(return_value=MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)))
        with patch(f"{MODULE}.EnvironmentVariables", env_mock), patch(
            f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()
        ), patch(f"{MODULE}.AsyncSGPClient") as mock_client_cls:
            from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
                SGPAsyncTracingProcessor,
            )

            disabled_config = SGPTracingProcessorConfig(sgp_api_key="", sgp_account_id="")
            processor = SGPAsyncTracingProcessor(disabled_config)

            assert processor.disabled is True
            assert processor.sgp_async_client is None, "Disabled processor must not construct a client"
            mock_client_cls.assert_not_called()

            span = _make_span()
            await processor.on_span_start(span)
            span.end_time = datetime.now(UTC)
            await processor.on_span_end(span)

            # No worker, no queue.
            assert processor._worker is None
            assert processor._queue is None

            # Shutdown is also a no-op.
            await processor.shutdown()

    async def test_shutdown_is_safe_when_called_multiple_times(self):
        """Shutdown must be idempotent: a second call after the worker has
        already exited cleanly should not raise, double-flush, or hang."""
        processor, client = TestSGPAsyncTracingProcessorBatching._make_processor()

        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()):
            span = _make_span()
            await processor.on_span_start(span)
            span.end_time = datetime.now(UTC)
            await processor.on_span_end(span)

        await processor.shutdown()
        first_call_count = client.spans.upsert_batch.call_count
        assert first_call_count == 1

        # Second shutdown: worker is already done; should not raise or
        # produce additional upserts since _spans is already cleared and
        # the queue has been drained.
        await processor.shutdown()
        assert client.spans.upsert_batch.call_count == first_call_count, (
            "Calling shutdown twice must not produce extra upserts"
        )

    async def test_shutdown_before_any_event_is_noop(self):
        """If shutdown runs before any span event, the worker was never
        started; it must early-return without spinning anything up just to
        tear it down."""
        env_mock = MagicMock(refresh=MagicMock(return_value=MagicMock(ACP_TYPE=None, AGENT_NAME=None, AGENT_ID=None)))
        with patch(f"{MODULE}.EnvironmentVariables", env_mock), patch(f"{MODULE}.AsyncSGPClient") as mock_client_cls:
            mock_client_cls.return_value = MagicMock(spans=MagicMock(upsert_batch=AsyncMock()))

            from agentex.lib.core.tracing.processors.sgp_tracing_processor import (
                SGPAsyncTracingProcessor,
            )

            processor = SGPAsyncTracingProcessor(_make_config())
            assert processor._worker is None

            await processor.shutdown()

            assert processor._worker is None, "Shutdown must not spin up a worker just to tear it down"

    async def test_apierror_triggers_retry_then_drops_batch_on_exhaustion(self):
        """`APIError` must be retried up to DEFAULT_RETRIES times. After
        exhaustion, the batch is dropped and the worker continues."""
        from scale_gp_beta import APIError

        processor, client = TestSGPAsyncTracingProcessorBatching._make_processor()

        # Make every attempt raise APIError so we exhaust the retry budget.
        api_error = APIError(message="boom", request=MagicMock(), body=None)
        client.spans.upsert_batch.side_effect = api_error

        # Patch sleep so retries don't block the test on real backoff timing.
        with patch(f"{MODULE}.create_span", side_effect=lambda **kw: _make_mock_sgp_span()), patch(
            "asyncio.sleep", new=AsyncMock()
        ):
            span = _make_span()
            await processor.on_span_start(span)
            span.end_time = datetime.now(UTC)
            await processor.on_span_end(span)

        await processor.shutdown()

        # 4 attempts, all failed. Batch dropped. Importantly, no fifth call.
        from agentex.lib.core.tracing.processors.sgp_tracing_processor import DEFAULT_RETRIES

        assert client.spans.upsert_batch.call_count == DEFAULT_RETRIES, (
            f"Expected exactly {DEFAULT_RETRIES} attempts before dropping; got {client.spans.upsert_batch.call_count}"
        )
