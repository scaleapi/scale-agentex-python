from typing import override

import pytest

from agentex.lib.core.harness.types import OpenSpan, CloseSpan
from agentex.lib.core.harness.tracer import SpanTracer

from ._fakes import FakeTracing, tool_marker


@pytest.mark.asyncio
async def test_open_then_close_starts_and_ends_span():
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="call_1", kind="tool", name="Bash", input={"cmd": "ls"}))
    await tracer.handle(CloseSpan(key="call_1", output="files", is_complete=True))
    assert fake.started == [("Bash", "p1", {"cmd": "ls"})]
    # A plain-string output is wrapped in a dict (SGP spans require an object).
    assert fake.ended == [("Bash", {"output": "files"})]


@pytest.mark.asyncio
async def test_non_dict_payloads_are_wrapped_in_a_dict():
    """SGP spans reject scalar input/output with a 422; the tracer wraps any
    non-dict payload so reasoning spans (string output) are not dropped."""
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="reasoning:0", kind="reasoning", name="reasoning", input={}))
    await tracer.handle(CloseSpan(key="reasoning:0", output="chain of thought", is_complete=True))
    # Empty-dict input stays a dict; string output is wrapped.
    assert fake.started == [("reasoning", "p1", {})]
    assert fake.ended == [("reasoning", {"output": "chain of thought"})]


@pytest.mark.asyncio
async def test_dict_and_none_payloads_pass_through_unchanged():
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="c", kind="tool", name="T", input={"a": 1}))
    await tracer.handle(CloseSpan(key="c", output={"result": "x"}, is_complete=True))
    await tracer.handle(OpenSpan(key="d", kind="tool", name="U", input={}))
    await tracer.handle(CloseSpan(key="d", output=None, is_complete=False))
    assert fake.ended == [("T", {"result": "x"}), ("U", None)]


@pytest.mark.asyncio
async def test_close_records_is_error_on_span_data():
    """A CloseSpan carrying is_error records the status on span.data (AGX1-371)."""
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="call_err", kind="tool", name="Bash", input={}))
    await tracer.handle(CloseSpan(key="call_err", output="boom", is_complete=True, is_error=True))
    assert fake.ended_spans[0].data == {**tool_marker("Bash"), "is_error": True}


@pytest.mark.asyncio
async def test_close_without_status_writes_no_is_error():
    """is_error=None (no status reported) must not write is_error to span.data."""
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="call_1", kind="tool", name="Bash", input={}))
    await tracer.handle(CloseSpan(key="call_1", output="files", is_complete=True))
    assert "is_error" not in fake.ended_spans[0].data


@pytest.mark.asyncio
async def test_successful_tool_span_is_marked_as_a_tool_call():
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="call_1", kind="tool", name="Bash", input={"cmd": "ls"}))
    await tracer.handle(CloseSpan(key="call_1", output="files", is_complete=True))
    assert fake.ended_spans[0].data == {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "Bash"}


@pytest.mark.asyncio
async def test_incomplete_tool_span_keeps_the_tool_marker():
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="call_1", kind="tool", name="Bash", input={}))
    await tracer.handle(CloseSpan(key="call_1", output=None, is_complete=False))
    assert fake.ended_spans[0].data == tool_marker("Bash")


@pytest.mark.asyncio
async def test_each_tool_span_names_its_own_tool():
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="a", kind="tool", name="Read", input={}))
    await tracer.handle(OpenSpan(key="b", kind="tool", name="Bash", input={}))
    await tracer.handle(CloseSpan(key="b", output="x"))
    await tracer.handle(CloseSpan(key="a", output="y"))
    assert [span.data for span in fake.ended_spans] == [tool_marker("Bash"), tool_marker("Read")]


@pytest.mark.asyncio
async def test_reasoning_span_is_not_marked_as_a_tool_call():
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="reasoning:0", kind="reasoning", name="reasoning", input={}))
    await tracer.handle(CloseSpan(key="reasoning:0", output="thought", is_complete=True))
    assert fake.ended_spans[0].data is None


@pytest.mark.asyncio
async def test_no_trace_id_is_noop():
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="", parent_span_id=None, tracing=fake)
    await tracer.handle(OpenSpan(key="k", kind="tool", name="X"))
    await tracer.handle(CloseSpan(key="k"))
    assert fake.started == [] and fake.ended == []


@pytest.mark.asyncio
async def test_tracing_failure_is_swallowed():
    class _Boom(FakeTracing):
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
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="t1", parent_span_id="p1", tracing=fake)
    await tracer.handle(OpenSpan(key="k", kind="tool", name="A"))
    await tracer.handle(OpenSpan(key="k", kind="tool", name="B"))
    await tracer.handle(CloseSpan(key="k"))
    # Both opens started spans, but only the second ("B") is closed.
    assert [name for name, _, _ in fake.started] == ["A", "B"]
    assert fake.ended == [("B", None)]
