import pytest

from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.types import OpenSpan, CloseSpan


class _FakeSpan:
    def __init__(self, name):
        self.name = name
        self.output = None


class _FakeTracing:
    def __init__(self):
        self.started = []
        self.ended = []

    async def start_span(self, *, trace_id, name, input=None, parent_id=None, data=None, task_id=None):
        self.started.append((name, parent_id, input))
        return _FakeSpan(name)

    async def end_span(self, *, trace_id, span):
        self.ended.append((span.name, span.output))


@pytest.mark.asyncio
async def test_open_then_close_starts_and_ends_span():
    fake = _FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="call_1", kind="tool", name="Bash", input={"cmd": "ls"}))
    await tracer.handle(CloseSpan(key="call_1", output="files", is_complete=True))
    assert fake.started == [("Bash", "p1", {"cmd": "ls"})]
    assert fake.ended == [("Bash", "files")]


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
        async def start_span(self, **kw):
            raise RuntimeError("backend down")

    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=_Boom())
    # Must not raise.
    await tracer.handle(OpenSpan(key="k", kind="tool", name="X"))
    await tracer.handle(CloseSpan(key="k"))
