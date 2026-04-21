from __future__ import annotations

from unittest.mock import MagicMock

from agentex.lib.core.tracing.trace import Trace, AsyncTrace


def _make_sync_trace(trace_id: str = "trace-123") -> tuple[MagicMock, Trace]:
    client = MagicMock()
    trace = Trace(processors=[], client=client, trace_id=trace_id)
    return client, trace


def _make_async_trace(trace_id: str = "trace-123") -> tuple[MagicMock, AsyncTrace]:
    client = MagicMock()
    trace = AsyncTrace(processors=[], client=client, trace_id=trace_id)
    return client, trace


class TestSyncTraceTaskId:
    def test_start_span_sets_task_id_on_span(self):
        _client, trace = _make_sync_trace()
        span = trace.start_span(name="foo", task_id="task-abc")
        assert span.task_id == "task-abc"
        assert span.trace_id == "trace-123"

    def test_start_span_defaults_task_id_to_none(self):
        _client, trace = _make_sync_trace()
        span = trace.start_span(name="foo")
        assert span.task_id is None

    def test_end_span_preserves_task_id_from_span(self):
        _client, trace = _make_sync_trace()
        span = trace.start_span(name="foo", task_id="task-abc")
        trace.end_span(span)
        assert span.task_id == "task-abc"


class TestAsyncTraceTaskId:
    async def test_start_span_sets_task_id_on_span(self):
        _client, trace = _make_async_trace()
        span = await trace.start_span(name="foo", task_id="task-abc")
        assert span.task_id == "task-abc"
        assert span.trace_id == "trace-123"

    async def test_start_span_defaults_task_id_to_none(self):
        _client, trace = _make_async_trace()
        span = await trace.start_span(name="foo")
        assert span.task_id is None

    async def test_end_span_preserves_task_id_from_span(self):
        _client, trace = _make_async_trace()
        span = await trace.start_span(name="foo", task_id="task-abc")
        await trace.end_span(span)
        assert span.task_id == "task-abc"
