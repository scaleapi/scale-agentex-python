"""Tests for the Gemini CLI stream-json -> Agentex StreamTaskMessage* converter."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from agentex.types.text_content import TextContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._gemini_cli_sync import convert_gemini_cli_to_agentex_events


async def _aiter(events: list[Any]) -> AsyncIterator[Any]:
    for e in events:
        yield e


async def _collect(stream: AsyncIterator[Any]) -> list[Any]:
    return [e async for e in stream]


def _init() -> dict[str, Any]:
    return {"type": "init", "timestamp": "t", "session_id": "sess-1", "model": "gemini-2.5-flash"}


def _user(text: str) -> dict[str, Any]:
    return {"type": "message", "timestamp": "t", "role": "user", "content": text}


def _delta(text: str) -> dict[str, Any]:
    return {"type": "message", "timestamp": "t", "role": "assistant", "content": text, "delta": True}


def _result(**stats: Any) -> dict[str, Any]:
    return {"type": "result", "timestamp": "t", "status": "success", "stats": stats}


class TestAssistantText:
    async def test_delta_chunks_become_one_start_deltas_done(self):
        out = await _collect(
            convert_gemini_cli_to_agentex_events(_aiter([_init(), _user("hi"), _delta("Hel"), _delta("lo"), _result()]))
        )
        assert [type(e) for e in out] == [
            StreamTaskMessageStart,
            StreamTaskMessageDelta,
            StreamTaskMessageDelta,
            StreamTaskMessageDone,
        ]
        assert isinstance(out[0].content, TextContent) and out[0].content.content == ""
        assert isinstance(out[1].delta, TextDelta) and out[1].delta.text_delta == "Hel"
        assert out[2].delta.text_delta == "lo"
        assert out[0].index == out[1].index == out[2].index == out[3].index

    async def test_user_message_is_ignored(self):
        out = await _collect(convert_gemini_cli_to_agentex_events(_aiter([_user("hello"), _result()])))
        assert out == []

    async def test_non_delta_assistant_message_is_delivered_whole(self):
        msg = {"type": "message", "role": "assistant", "content": "Whole answer"}
        out = await _collect(convert_gemini_cli_to_agentex_events(_aiter([msg])))
        assert [type(e) for e in out] == [StreamTaskMessageStart, StreamTaskMessageDelta, StreamTaskMessageDone]
        assert out[1].delta.text_delta == "Whole answer"

    async def test_materialised_message_closes_open_streamed_slot_without_duplicating(self):
        out = await _collect(
            convert_gemini_cli_to_agentex_events(
                _aiter([_delta("Hel"), _delta("lo"), {"type": "message", "role": "assistant", "content": "Hello"}])
            )
        )
        assert [type(e) for e in out] == [
            StreamTaskMessageStart,
            StreamTaskMessageDelta,
            StreamTaskMessageDelta,
            StreamTaskMessageDone,
        ]

    async def test_stream_ending_without_result_still_closes_the_slot(self):
        out = await _collect(convert_gemini_cli_to_agentex_events(_aiter([_delta("partial")])))
        assert isinstance(out[-1], StreamTaskMessageDone)

    async def test_raw_json_strings_and_junk_lines(self):
        lines = [json.dumps(_delta("A")), "", "not json", json.dumps(_result())]
        out = await _collect(convert_gemini_cli_to_agentex_events(_aiter(lines)))
        assert [type(e) for e in out] == [StreamTaskMessageStart, StreamTaskMessageDelta, StreamTaskMessageDone]


class TestTools:
    async def test_tool_use_and_result_pair_by_tool_id(self):
        events = [
            _delta("Let me check."),
            {"type": "tool_use", "tool_name": "read_file", "tool_id": "call-1", "parameters": {"path": "a.txt"}},
            {"type": "tool_result", "tool_id": "call-1", "status": "success", "output": "file body"},
            _delta("Done."),
            _result(),
        ]
        out = await _collect(convert_gemini_cli_to_agentex_events(_aiter(events)))
        kinds = [type(e).__name__ for e in out]
        # text slot closed before the tool request; a second slot opened after the result
        assert kinds == [
            "StreamTaskMessageStart",
            "StreamTaskMessageDelta",
            "StreamTaskMessageDone",
            "StreamTaskMessageStart",
            "StreamTaskMessageDone",
            "StreamTaskMessageFull",
            "StreamTaskMessageStart",
            "StreamTaskMessageDelta",
            "StreamTaskMessageDone",
        ]
        req = out[3].content
        assert isinstance(req, ToolRequestContent)
        assert req.tool_call_id == "call-1" and req.name == "read_file" and req.arguments == {"path": "a.txt"}
        res = out[5].content
        assert isinstance(res, ToolResponseContent)
        assert res.tool_call_id == "call-1" and res.content == {"result": "file body"}
        assert out[3].index == out[4].index and out[5].index not in (out[0].index, out[3].index)

    async def test_error_tool_result_sets_is_error_and_uses_message(self):
        events = [
            {"type": "tool_use", "tool_name": "run_shell_command", "tool_id": "call-2", "parameters": {}},
            {
                "type": "tool_result",
                "tool_id": "call-2",
                "status": "error",
                "error": {"type": "ToolError", "message": "denied"},
            },
        ]
        out = await _collect(convert_gemini_cli_to_agentex_events(_aiter(events)))
        full = [e for e in out if isinstance(e, StreamTaskMessageFull)][0]
        assert full.content.content == {"result": "denied", "is_error": True}

    async def test_missing_tool_id_gets_a_synthetic_one(self):
        out = await _collect(
            convert_gemini_cli_to_agentex_events(_aiter([{"type": "tool_use", "tool_name": "x", "parameters": {}}]))
        )
        assert out[0].content.tool_call_id == "tool_1"


class TestCallbacks:
    async def test_on_init_and_on_result_receive_raw_events(self):
        seen: dict[str, Any] = {}

        async def on_init(evt: dict[str, Any]) -> None:
            seen["init"] = evt

        async def on_result(evt: dict[str, Any]) -> None:
            seen["result"] = evt

        await _collect(
            convert_gemini_cli_to_agentex_events(
                _aiter([_init(), _delta("x"), _result(total_tokens=3)]), on_result=on_result, on_init=on_init
            )
        )
        assert seen["init"]["session_id"] == "sess-1"
        assert seen["result"]["stats"]["total_tokens"] == 3

    async def test_error_events_emit_nothing(self):
        out = await _collect(
            convert_gemini_cli_to_agentex_events(
                _aiter([{"type": "error", "severity": "warning", "message": "slow"}, _result()])
            )
        )
        assert out == []

    async def test_closing_the_generator_closes_the_source(self):
        closed = {"v": False}

        class _Src:
            def __init__(self) -> None:
                self._it = _aiter([_delta("a"), _delta("b"), _result()])

            def __aiter__(self):
                return self

            async def __anext__(self):
                return await self._it.__anext__()

            async def aclose(self) -> None:
                closed["v"] = True

        gen = convert_gemini_cli_to_agentex_events(_Src())
        await gen.__anext__()
        await gen.aclose()
        assert closed["v"] is True
