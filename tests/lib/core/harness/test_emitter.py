import pytest

from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.lib.core.harness.types import TurnUsage
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)

from ._fakes import FakeTracing


class _FakeCtx:
    """Minimal StreamingTaskMessageContext fake (see test_auto_send.py)."""

    def __init__(self, sink, content_type, initial_content):
        self.sink = sink
        self.content_type = content_type
        self.task_message = TaskMessage(id="msg-1", task_id="task1", content=initial_content)

    async def __aenter__(self):
        self.sink.append(("open", self.content_type))
        return self

    async def __aexit__(self, *a):
        await self.close()
        return False

    async def close(self):
        self.sink.append(("close", self.content_type))

    async def stream_update(self, update):
        self.sink.append(("update", update))
        return update


class _FakeStreaming:
    def __init__(self):
        self.sink = []

    def streaming_task_message_context(self, task_id, initial_content, streaming_mode="coalesced", created_at=None):
        ctype = getattr(initial_content, "type", None)
        self.sink.append(("ctx", ctype))
        return _FakeCtx(self.sink, ctype, initial_content)


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
        StreamTaskMessageStart(type="start", index=0, content=TextContent(type="text", author="agent", content="hi")),
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
    emitter = UnifiedEmitter(task_id="t", trace_id="trace1", parent_span_id="p", tracing=FakeTracing())
    assert emitter.tracer is not None


@pytest.mark.asyncio
async def test_emitter_tracing_overridable_off():
    emitter = UnifiedEmitter(task_id="t", trace_id="trace1", parent_span_id="p", tracer=False)
    assert emitter.tracer is None


@pytest.mark.asyncio
async def test_emitter_auto_send_turn_returns_usage():
    usage = TurnUsage(model="m", input_tokens=5)
    events = [
        StreamTaskMessageStart(type="start", index=0, content=TextContent(type="text", author="agent", content="")),
        StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="Hello")),
        StreamTaskMessageDone(type="done", index=0),
    ]
    turn = _Turn(events, usage)
    fake = _FakeStreaming()
    emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None, streaming=fake)
    result = await emitter.auto_send_turn(turn)
    assert result.usage == usage
    assert result.final_text == "Hello"


class _ContractTurn:
    """A turn that honors the single-pass contract: usage() is the empty default
    UNTIL `events` is exhausted, then the real usage (this is how real harness
    turns behave — they populate usage while the stream is consumed)."""

    def __init__(self, events_list, real_usage):
        self._events_list = events_list
        self._real_usage = real_usage
        self._exhausted = False

    @property
    async def events(self):
        for e in self._events_list:
            yield e
        self._exhausted = True

    def usage(self):
        return self._real_usage if self._exhausted else TurnUsage(model="m")


@pytest.mark.asyncio
async def test_emitter_auto_send_turn_reads_usage_after_exhaustion():
    # Regression: auto_send_turn must read turn.usage() AFTER consuming the
    # stream, not eagerly when building the auto_send call (which would capture
    # the empty default and lose real token usage on the auto_send path).
    real_usage = TurnUsage(model="m", input_tokens=11, output_tokens=22, total_tokens=33, num_llm_calls=2)
    events = [
        StreamTaskMessageStart(type="start", index=0, content=TextContent(type="text", author="agent", content="")),
        StreamTaskMessageDelta(type="delta", index=0, delta=TextDelta(type="text", text_delta="hi")),
        StreamTaskMessageDone(type="done", index=0),
    ]
    turn = _ContractTurn(events, real_usage)
    emitter = UnifiedEmitter(task_id="t", trace_id=None, parent_span_id=None, streaming=_FakeStreaming())
    result = await emitter.auto_send_turn(turn)
    assert result.usage == real_usage
    assert result.usage.input_tokens == 11 and result.usage.total_tokens == 33
