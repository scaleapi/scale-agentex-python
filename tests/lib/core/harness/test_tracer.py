from typing import override

import pytest

from agentex.lib.core.harness.types import OpenSpan, CloseSpan
from agentex.lib.core.harness.tracer import SpanTracer


class _FakeSpan:
    def __init__(self, name):
        self.name = name
        self.output = None
        self.data = None


class _FakeTracing:
    def __init__(self):
        self.started = []
        self.ended = []
        self.ended_spans = []

    async def start_span(self, *, trace_id, name, input=None, parent_id=None, data=None, task_id=None):
        self.started.append((name, parent_id, input))
        return _FakeSpan(name)

    async def end_span(self, *, trace_id, span):
        self.ended.append((span.name, span.output))
        self.ended_spans.append(span)


@pytest.mark.asyncio
async def test_open_then_close_starts_and_ends_span():
    fake = _FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="call_1", kind="tool", name="Bash", input={"cmd": "ls"}))
    await tracer.handle(CloseSpan(key="call_1", output="files", is_complete=True))
    assert fake.started == [("Bash", "p1", {"cmd": "ls"})]
    assert fake.ended == [("Bash", "files")]


@pytest.mark.asyncio
async def test_close_records_is_error_on_span_data():
    """A CloseSpan carrying is_error records the status on span.data (AGX1-371)."""
    fake = _FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="call_err", kind="tool", name="Bash", input={}))
    await tracer.handle(CloseSpan(key="call_err", output="boom", is_complete=True, is_error=True))
    assert fake.ended_spans[0].data == {"is_error": True}


@pytest.mark.asyncio
async def test_close_without_status_leaves_span_data_untouched():
    """is_error=None (no status reported) must not write to span.data."""
    fake = _FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="call_1", kind="tool", name="Bash", input={}))
    await tracer.handle(CloseSpan(key="call_1", output="files", is_complete=True))
    assert fake.ended_spans[0].data is None


@pytest.mark.asyncio
async def test_no_trace_id_is_noop():
    fake = _FakeTracing()
    tracer = SpanTracer(trace_id="", parent_span_id=None, tracing=fake)
    await tracer.handle(OpenSpan(key="k", kind="tool", name="X"))
    await tracer.handle(CloseSpan(key="k"))
    assert fake.started == [] and fake.ended == []


@pytest.mark.asyncio
async def test_tracing_failure_is_swallowed():
    class _Boom(_FakeTracing):
        @override
        async def start_span(self, **kw):
            raise RuntimeError("backend down")

    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=_Boom())
    # Must not raise.
    await tracer.handle(OpenSpan(key="k", kind="tool", name="X"))
    await tracer.handle(CloseSpan(key="k"))
    assert tracer._open == {}


@pytest.mark.asyncio
async def test_duplicate_open_replaces_silently():
    fake = _FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="k", kind="tool", name="A"))
    await tracer.handle(OpenSpan(key="k", kind="tool", name="B"))
    await tracer.handle(CloseSpan(key="k"))
    # Both opens started spans, but only the second ("B") is closed.
    assert [name for name, _, _ in fake.started] == ["A", "B"]
    assert fake.ended == [("B", None)]
