from agentex.lib.core.harness.span_derivation import SpanDeriver
from agentex.lib.core.harness.types import OpenSpan, CloseSpan
from agentex.types.task_message_update import (
    StreamTaskMessageStart,
    StreamTaskMessageDelta,
    StreamTaskMessageFull,
    StreamTaskMessageDone,
)
from agentex.types.text_content import TextContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.types.tool_request_delta import ToolRequestDelta


def _signals(deriver, events):
    out = []
    for e in events:
        out.extend(deriver.observe(e))
    out.extend(deriver.flush())
    return out


def _tool_req(idx, tcid, name, args):
    return StreamTaskMessageStart(
        type="start", index=idx,
        content=ToolRequestContent(type="tool_request", author="agent",
                                   tool_call_id=tcid, name=name, arguments=args),
    )


def test_text_only_yields_no_spans():
    d = SpanDeriver()
    events = [
        StreamTaskMessageStart(type="start", index=0,
            content=TextContent(type="text", author="agent", content="")),
        StreamTaskMessageDelta(type="delta", index=0,
            delta=None),
        StreamTaskMessageDone(type="done", index=0),
    ]
    assert _signals(d, events) == []


def test_single_tool_opens_on_done_closes_on_response():
    d = SpanDeriver()
    events = [
        _tool_req(0, "call_1", "Bash", {"cmd": "ls"}),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageFull(type="full", index=1,
            content=ToolResponseContent(type="tool_response", author="agent",
                                        tool_call_id="call_1", name="Bash", content="files")),
    ]
    sigs = _signals(d, events)
    assert sigs == [
        OpenSpan(key="call_1", kind="tool", name="Bash", input={"cmd": "ls"}),
        CloseSpan(key="call_1", output="files", is_complete=True),
    ]


def test_reasoning_opens_on_start_closes_on_done():
    d = SpanDeriver()
    events = [
        StreamTaskMessageStart(type="start", index=0,
            content=ReasoningContent(type="reasoning", author="agent", summary=[], content=[])),
        StreamTaskMessageDone(type="done", index=0),
    ]
    sigs = _signals(d, events)
    assert sigs[0] == OpenSpan(key="reasoning:0", kind="reasoning", name="reasoning", input={})
    assert sigs[1] == CloseSpan(key="reasoning:0", output=None, is_complete=True)


def test_parallel_tools_pair_by_tool_call_id():
    d = SpanDeriver()
    events = [
        _tool_req(0, "a", "T1", {}),
        _tool_req(1, "b", "T2", {}),
        StreamTaskMessageDone(type="done", index=0),
        StreamTaskMessageDone(type="done", index=1),
        StreamTaskMessageFull(type="full", index=2,
            content=ToolResponseContent(type="tool_response", author="agent",
                                        tool_call_id="b", name="T2", content="rb")),
        StreamTaskMessageFull(type="full", index=3,
            content=ToolResponseContent(type="tool_response", author="agent",
                                        tool_call_id="a", name="T1", content="ra")),
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
        StreamTaskMessageStart(type="start", index=0,
            content=ToolRequestContent(type="tool_request", author="agent",
                                       tool_call_id="c", name="Bash", arguments={})),
        StreamTaskMessageDelta(type="delta", index=0,
            delta=ToolRequestDelta(type="tool_request", tool_call_id="c", name="Bash",
                                   arguments_delta='{"cmd":')),
        StreamTaskMessageDelta(type="delta", index=0,
            delta=ToolRequestDelta(type="tool_request", tool_call_id="c", name="Bash",
                                   arguments_delta='"ls"}')),
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
        StreamTaskMessageStart(type="start", index=None,
            content=ToolRequestContent(type="tool_request", author="agent",
                                       tool_call_id="n", name="Bash", arguments={})),
        StreamTaskMessageDone(type="done", index=None),
    ]
    assert _signals(d, events) == []


def test_orphan_tool_response_ignored():
    d = SpanDeriver()
    events = [
        StreamTaskMessageFull(type="full", index=0,
            content=ToolResponseContent(type="tool_response", author="agent",
                                        tool_call_id="z", name="Bash", content="r")),
    ]
    assert _signals(d, events) == []
