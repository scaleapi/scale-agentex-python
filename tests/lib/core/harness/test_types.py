from typing import AsyncIterator

from agentex.lib.core.harness.types import (
    OpenSpan,
    CloseSpan,
    TurnUsage,
    TurnResult,
    HarnessTurn,
    StreamTaskMessage,
)


def test_open_close_span_construct():
    o = OpenSpan(key="call_1", kind="tool", name="Bash", input={"cmd": "ls"})
    c = CloseSpan(key="call_1", output="files", is_complete=True)
    assert o.key == c.key == "call_1"
    assert o.kind == "tool"
    assert c.is_complete is True


def test_turn_usage_defaults_are_none():
    u = TurnUsage(model="claude-opus-4-6")
    assert u.model == "claude-opus-4-6"
    assert u.input_tokens is None
    assert u.num_tool_calls == 0


def test_turn_result_wraps_usage():
    r = TurnResult(final_text="hi", usage=TurnUsage(model="m"))
    assert r.final_text == "hi"
    assert r.usage.model == "m"


def test_close_span_defaults():
    c = CloseSpan(key="x")
    assert c.output is None
    assert c.is_complete is True


def test_harness_turn_runtime_check():
    class _Turn:
        @property
        def events(self) -> AsyncIterator[StreamTaskMessage]:
            async def _gen() -> AsyncIterator[StreamTaskMessage]:
                if False:
                    yield  # pragma: no cover

            return _gen()

        def usage(self) -> TurnUsage:
            return TurnUsage(model="m")

    assert isinstance(_Turn(), HarnessTurn) is True
