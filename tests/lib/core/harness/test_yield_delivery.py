import pytest

from agentex.lib.core.harness.tracer import SpanTracer
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.core.harness.yield_delivery import yield_events

from ._fakes import FakeTracing


async def _gen(events):
    for e in events:
        yield e


@pytest.mark.asyncio
async def test_yield_passes_events_through_and_traces():
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="t", parent_span_id="p", tracing=fake)
    events = [
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=ToolRequestContent(
                type="tool_request", author="agent", tool_call_id="c", name="Bash", arguments={}
            ),
        ),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageFull(
            type="full",
            index=1,
            content=ToolResponseContent(
                type="tool_response", author="agent", tool_call_id="c", name="Bash", content="ok"
            ),
        ),
    ]
    out = [e async for e in yield_events(_gen(events), tracer=tracer)]
    assert out == events  # passthrough unchanged
    assert fake.started_names == ["Bash"]  # span derived + opened
    assert fake.ended_outputs == ["ok"]  # span closed with response


@pytest.mark.asyncio
async def test_yield_without_tracer_is_pure_passthrough():
    events = [
        StreamTaskMessageDone(type="done", index=0),
    ]
    out = [e async for e in yield_events(_gen(events), tracer=None)]
    assert out == events


@pytest.mark.asyncio
async def test_flush_runs_on_early_close():
    fake = FakeTracing()
    tracer = SpanTracer(trace_id="t", parent_span_id="p", tracing=fake)
    events = [
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=ToolRequestContent(
                type="tool_request", author="agent", tool_call_id="c", name="Bash", arguments={}
            ),
        ),
        StreamTaskMessageDone(type="done", index=0),
        # response intentionally never arrives
    ]
    gen = yield_events(_gen(events), tracer=tracer)
    first = await gen.__anext__()  # Start
    second = await gen.__anext__()  # Done -> tool span opens here
    await gen.aclose()  # triggers the finally -> flush()
    assert fake.started_names == ["Bash"]
    assert fake.ended_outputs == [None]  # flush closed the unpaired span (incomplete, no output)
