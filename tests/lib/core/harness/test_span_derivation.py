from agentex.types.text_content import TextContent
from agentex.lib.core.harness.types import OpenSpan, CloseSpan
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.tool_request_delta import ToolRequestDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.types.reasoning_content_delta import ReasoningContentDelta
from agentex.types.reasoning_summary_delta import ReasoningSummaryDelta
from agentex.lib.core.harness.span_derivation import SpanDeriver


def _signals(deriver, events):
    out = []
    for e in events:
        out.extend(deriver.observe(e))
    out.extend(deriver.flush())
    return out


def _tool_req(idx, tcid, name, args):
    return StreamTaskMessageStart(
        type="start",
        index=idx,
        content=ToolRequestContent(type="tool_request", author="agent", tool_call_id=tcid, name=name, arguments=args),
    )


def test_text_only_yields_no_spans():
    d = SpanDeriver()
    events = [
        StreamTaskMessageStart(type="start", index=0, content=TextContent(type="text", author="agent", content="")),
        StreamTaskMessageDelta(type="delta", index=0, delta=None),
        StreamTaskMessageDone(type="done", index=0),
    ]
    assert _signals(d, events) == []


def test_single_tool_opens_on_done_closes_on_response():
    d = SpanDeriver()
    events = [
        _tool_req(0, "call_1", "Bash", {"cmd": "ls"}),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageFull(
            type="full",
            index=1,
            content=ToolResponseContent(
                type="tool_response", author="agent", tool_call_id="call_1", name="Bash", content="files"
            ),
        ),
    ]
    sigs = _signals(d, events)
    assert sigs == [
        OpenSpan(key="call_1", kind="tool", name="Bash", input={"cmd": "ls"}),
        CloseSpan(key="call_1", output="files", is_complete=True),
    ]
    # No status reported -> CloseSpan carries is_error=None.
    assert sigs[1].is_error is None


def test_tool_response_is_error_propagates_to_close_span():
    """ToolResponseContent.is_error flows onto the CloseSpan so a derived tool
    span can be marked as a failure (AGX1-371)."""
    d = SpanDeriver()
    events = [
        _tool_req(0, "call_err", "Bash", {"cmd": "false"}),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageFull(
            type="full",
            index=1,
            content=ToolResponseContent(
                type="tool_response",
                author="agent",
                tool_call_id="call_err",
                name="Bash",
                content="boom",
                is_error=True,
            ),
        ),
    ]
    sigs = _signals(d, events)
    assert sigs == [
        OpenSpan(key="call_err", kind="tool", name="Bash", input={"cmd": "false"}),
        CloseSpan(key="call_err", output="boom", is_complete=True, is_error=True),
    ]


def test_reasoning_opens_on_start_closes_on_done():
    d = SpanDeriver()
    events = [
        StreamTaskMessageStart(
            type="start", index=0, content=ReasoningContent(type="reasoning", author="agent", summary=[], content=[])
        ),
        StreamTaskMessageDone(type="done", index=0),
    ]
    sigs = _signals(d, events)
    assert sigs[0] == OpenSpan(key="reasoning:0", kind="reasoning", name="reasoning", input={})
    # No deltas -> nothing to record, so output stays None (not an empty string).
    assert sigs[1] == CloseSpan(key="reasoning:0", output=None, is_complete=True)


def test_reasoning_content_deltas_recorded_as_output():
    """The chain-of-thought streamed via ReasoningContentDelta lands on the
    reasoning span's output (previously dropped, leaving the span blank)."""
    d = SpanDeriver()
    events = [
        StreamTaskMessageStart(
            type="start", index=0, content=ReasoningContent(type="reasoning", author="agent", summary=[], content=[])
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=ReasoningContentDelta(type="reasoning_content", content_index=0, content_delta="Let me "),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=ReasoningContentDelta(type="reasoning_content", content_index=0, content_delta="think."),
        ),
        StreamTaskMessageDone(type="done", index=0),
    ]
    sigs = _signals(d, events)
    assert sigs[0] == OpenSpan(key="reasoning:0", kind="reasoning", name="reasoning", input={})
    assert sigs[1] == CloseSpan(key="reasoning:0", output="Let me think.", is_complete=True)


def test_reasoning_summary_deltas_recorded_as_output():
    """Reasoning-model summary deltas (o-series) also land on the span output."""
    d = SpanDeriver()
    events = [
        StreamTaskMessageStart(
            type="start", index=0, content=ReasoningContent(type="reasoning", author="agent", summary=[], content=[])
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=ReasoningSummaryDelta(type="reasoning_summary", summary_index=0, summary_delta="Summary text"),
        ),
        StreamTaskMessageDone(type="done", index=0),
    ]
    sigs = _signals(d, events)
    assert sigs[1] == CloseSpan(key="reasoning:0", output="Summary text", is_complete=True)


def test_reasoning_text_seeded_from_start_content():
    """A non-streaming harness that carries the full thinking on the Start
    content still records it as output even with no deltas."""
    d = SpanDeriver()
    events = [
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=ReasoningContent(type="reasoning", author="agent", summary=[], content=["full thought"]),
        ),
        StreamTaskMessageDone(type="done", index=0),
    ]
    sigs = _signals(d, events)
    assert sigs[1] == CloseSpan(key="reasoning:0", output="full thought", is_complete=True)


def test_reasoning_unclosed_flushes_with_text():
    """An unclosed reasoning span flushes incomplete but still carries its text."""
    d = SpanDeriver()
    events = [
        StreamTaskMessageStart(
            type="start", index=0, content=ReasoningContent(type="reasoning", author="agent", summary=[], content=[])
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=ReasoningContentDelta(type="reasoning_content", content_index=0, content_delta="partial"),
        ),
    ]
    sigs = _signals(d, events)
    assert sigs[-1] == CloseSpan(key="reasoning:0", output="partial", is_complete=False)


def test_parallel_tools_pair_by_tool_call_id():
    d = SpanDeriver()
    events = [
        _tool_req(0, "a", "T1", {}),
        _tool_req(1, "b", "T2", {}),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageDone(type="done", index=1),
        StreamTaskMessageFull(
            type="full",
            index=2,
            content=ToolResponseContent(
                type="tool_response", author="agent", tool_call_id="b", name="T2", content="rb"
            ),
        ),
        StreamTaskMessageFull(
            type="full",
            index=3,
            content=ToolResponseContent(
                type="tool_response", author="agent", tool_call_id="a", name="T1", content="ra"
            ),
        ),
    ]
    sigs = _signals(d, events)
    opens = [s for s in sigs if isinstance(s, OpenSpan)]
    closes = [s for s in sigs if isinstance(s, CloseSpan)]
    assert {o.key for o in opens} == {"a", "b"}
    assert [c.key for c in closes] == ["b", "a"]
    assert all(c.is_complete for c in closes)


def test_streamed_args_accumulate_into_open_input():
    d = SpanDeriver()
    events = [
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=ToolRequestContent(
                type="tool_request", author="agent", tool_call_id="c", name="Bash", arguments={}
            ),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=ToolRequestDelta(type="tool_request", tool_call_id="c", name="Bash", arguments_delta='{"cmd":'),
        ),
        StreamTaskMessageDelta(
            type="delta",
            index=0,
            delta=ToolRequestDelta(type="tool_request", tool_call_id="c", name="Bash", arguments_delta='"ls"}'),
        ),
        StreamTaskMessageDone(type="done", index=0),
    ]
    sigs = _signals(d, events)
    assert sigs[0] == OpenSpan(key="c", kind="tool", name="Bash", input={"cmd": "ls"})


def test_unclosed_tool_closed_incomplete_on_flush():
    d = SpanDeriver()
    events = [
        _tool_req(0, "x", "Bash", {}),
        StreamTaskMessageDone(type="done", index=0),
    ]
    sigs = _signals(d, events)
    assert sigs[0] == OpenSpan(key="x", kind="tool", name="Bash", input={})
    assert sigs[1] == CloseSpan(key="x", output=None, is_complete=False)


def test_none_index_is_skipped():
    d = SpanDeriver()
    events = [
        StreamTaskMessageStart(
            type="start",
            index=None,
            content=ToolRequestContent(
                type="tool_request", author="agent", tool_call_id="n", name="Bash", arguments={}
            ),
        ),
        StreamTaskMessageDone(type="done", index=None),
    ]
    assert _signals(d, events) == []


def test_orphan_tool_response_ignored():
    d = SpanDeriver()
    events = [
        StreamTaskMessageFull(
            type="full",
            index=0,
            content=ToolResponseContent(
                type="tool_response", author="agent", tool_call_id="z", name="Bash", content="r"
            ),
        ),
    ]
    assert _signals(d, events) == []


def test_full_tool_request_opens_span():
    """Full(ToolRequestContent) must open a tool span (for LangGraph-style harnesses)."""
    d = SpanDeriver()
    events = [
        StreamTaskMessageFull(
            type="full",
            index=0,
            content=ToolRequestContent(
                type="tool_request",
                author="agent",
                tool_call_id="call_x",
                name="Bash",
                arguments={"cmd": "ls"},
            ),
        ),
    ]
    sigs = _signals(d, events)
    assert sigs[0] == OpenSpan(key="call_x", kind="tool", name="Bash", input={"cmd": "ls"})
    assert sigs[1] == CloseSpan(key="call_x", output=None, is_complete=False)


def test_full_tool_request_and_response_paired():
    """Full(ToolRequestContent) + Full(ToolResponseContent) produces a complete span pair."""
    d = SpanDeriver()
    events = [
        StreamTaskMessageFull(
            type="full",
            index=0,
            content=ToolRequestContent(
                type="tool_request",
                author="agent",
                tool_call_id="call_y",
                name="Grep",
                arguments={},
            ),
        ),
        StreamTaskMessageFull(
            type="full",
            index=1,
            content=ToolResponseContent(
                type="tool_response",
                author="agent",
                tool_call_id="call_y",
                name="Grep",
                content="result",
            ),
        ),
    ]
    sigs = _signals(d, events)
    assert sigs == [
        OpenSpan(key="call_y", kind="tool", name="Grep", input={}),
        CloseSpan(key="call_y", output="result", is_complete=True),
    ]


def test_full_tool_request_does_not_double_open():
    """A Full(ToolRequestContent) for an already-open tool_call_id is a no-op."""
    d = SpanDeriver()
    events = [
        StreamTaskMessageStart(
            type="start",
            index=0,
            content=ToolRequestContent(
                type="tool_request",
                author="agent",
                tool_call_id="call_z",
                name="X",
                arguments={},
            ),
        ),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageFull(
            type="full",
            index=1,
            content=ToolRequestContent(
                type="tool_request",
                author="agent",
                tool_call_id="call_z",
                name="X",
                arguments={},
            ),
        ),
    ]
    sigs = _signals(d, events)
    opens = [s for s in sigs if isinstance(s, OpenSpan)]
    assert len(opens) == 1
    assert opens[0].key == "call_z"
