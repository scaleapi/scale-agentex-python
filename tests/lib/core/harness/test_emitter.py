import pytest

from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.lib.core.harness.types import TurnUsage
from agentex.types.task_message_update import StreamTaskMessageStart, StreamTaskMessageDone
from agentex.types.text_content import TextContent


class _FakeTracing:
    async def start_span(self, **kw):
        return None

    async def end_span(self, **kw):
        pass


class _Turn:
    def __init__(self, events_list, usage):
        self._events_list = events_list
        self._usage = usage

    @property
    async def events(self):
        for e in self._events_list:
            yield e

    def usage(self):
        return self._usage


@pytest.mark.asyncio
async def test_emitter_yield_mode_passes_through():
    events = [
        StreamTaskMessageStart(type="start", index=0,
            content=TextContent(type="text", author="agent", content="hi")),
        StreamTaskMessageDone(type="done", index=0),
    ]
    turn = _Turn(events, TurnUsage(model="m"))
    emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None)
    out = [e async for e in emitter.yield_turn(turn)]
    assert out == events


@pytest.mark.asyncio
async def test_emitter_tracing_default_on_when_trace_id_present():
    # Inject a fake tracing backend so the test env doesn't need temporalio.
    # This exercises the default-on path (tracer=None) when trace_id is truthy.
    emitter = UnifiedEmitter(task_id="t", trace_id="trace1", parent_span_id="p",
                             tracing=_FakeTracing())
    assert emitter.tracer is not None


@pytest.mark.asyncio
async def test_emitter_tracing_overridable_off():
    emitter = UnifiedEmitter(task_id="t", trace_id="trace1", parent_span_id="p", tracer=False)
    assert emitter.tracer is None
