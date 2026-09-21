from __future__ import annotations

import uuid
import logging
from typing import override
from datetime import UTC, datetime

from agentex.types.span import Span
from agentex.lib.types.tracing import TracingProcessorConfig
from agentex.lib.core.tracing.processors.tracing_processor_interface import (
    AsyncTracingProcessor,
)


def _make_span(span_id: str | None = None) -> Span:
    return Span(
        id=span_id or str(uuid.uuid4()),
        name="test-span",
        start_time=datetime.now(UTC),
        trace_id="trace-1",
    )


class _RecordingProcessor(AsyncTracingProcessor):
    """Test processor that records every on_span_* call and fails on demand."""

    def __init__(self, fail_ids: set[str] | None = None) -> None:
        self.started_ids: list[str] = []
        self.ended_ids: list[str] = []
        self._fail_ids = fail_ids or set()

    @override
    async def on_span_start(self, span: Span) -> None:
        self.started_ids.append(span.id)
        if span.id in self._fail_ids:
            raise RuntimeError(f"boom-start-{span.id}")

    @override
    async def on_span_end(self, span: Span) -> None:
        self.ended_ids.append(span.id)
        if span.id in self._fail_ids:
            raise RuntimeError(f"boom-end-{span.id}")

    @override
    async def shutdown(self) -> None:
        pass


class TestDefaultBatchedFanout:
    """The default on_spans_start / on_spans_end in AsyncTracingProcessor must:
    - dispatch to the single-span method for every span
    - continue after individual failures (not short-circuit)
    - log each failure individually
    - not propagate exceptions to the caller
    """

    async def test_on_spans_start_runs_every_span_despite_failures(self, caplog):
        proc = _RecordingProcessor(fail_ids={"span-1"})
        spans = [_make_span(f"span-{i}") for i in range(3)]

        with caplog.at_level(logging.ERROR):
            # Must not raise, even though span-1 fails.
            await proc.on_spans_start(spans)

        # Every span's on_span_start was invoked
        assert proc.started_ids == ["span-0", "span-1", "span-2"]

    async def test_on_spans_start_logs_each_failure(self, caplog):
        proc = _RecordingProcessor(fail_ids={"span-0", "span-2"})
        spans = [_make_span(f"span-{i}") for i in range(3)]

        with caplog.at_level(logging.ERROR):
            await proc.on_spans_start(spans)

        # Two distinct error log records, one per failing span
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        messages = " ".join(r.getMessage() for r in error_records)
        assert "span-0" in messages
        assert "span-2" in messages

    async def test_on_spans_end_runs_every_span_despite_failures(self, caplog):
        proc = _RecordingProcessor(fail_ids={"span-1"})
        spans = [_make_span(f"span-{i}") for i in range(3)]

        with caplog.at_level(logging.ERROR):
            await proc.on_spans_end(spans)

        assert proc.ended_ids == ["span-0", "span-1", "span-2"]

    async def test_dummy_config_construction(self):
        """AsyncTracingProcessor's __init__ is abstract — verify concrete
        subclass above satisfies the interface."""
        _ = TracingProcessorConfig
        proc = _RecordingProcessor()
        await proc.on_spans_start([])
        await proc.on_spans_end([])
        assert proc.started_ids == []
        assert proc.ended_ids == []
