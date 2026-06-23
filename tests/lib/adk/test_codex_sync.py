"""Offline tests for the codex event-stream parser tap.

Tests cover:
- Text streaming (agent_message items)
- Tool call streaming (command_execution, mcp_tool_call, file_change)
- Reasoning streaming (reasoning items)
- Multi-step turns
- Error events (top-level + item-level)
- Edge cases: empty events, non-JSON lines, unknown types
- on_result callback (session_id, usage, counters)
- file_change synthesized start (no item.started emitted by codex)
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from agentex.types.reasoning_content import ReasoningContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.task_message_content import TextContent
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._codex_sync import (
    _truncate,
    _tool_args_for,
    _tool_name_for,
    _tool_output_for,
    convert_codex_to_agentex_events,
)
from agentex.types.reasoning_content_delta import ReasoningContentDelta
from agentex.types.reasoning_summary_delta import ReasoningSummaryDelta


async def _aiter(items: list[Any]) -> AsyncIterator[Any]:
    for item in items:
        yield item


async def _collect(stream: AsyncIterator[Any]) -> list[Any]:
    return [e async for e in stream]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_truncate_short(self) -> None:
        assert _truncate("hello", max_len=10) == "hello"

    def test_truncate_long(self) -> None:
        assert _truncate("a" * 5000) == "a" * 4000

    def test_tool_name_command_execution(self) -> None:
        assert _tool_name_for("command_execution", {}) == "bash"

    def test_tool_name_file_change(self) -> None:
        assert _tool_name_for("file_change", {}) == "file_change"

    def test_tool_name_mcp_with_server_and_tool(self) -> None:
        assert _tool_name_for("mcp_tool_call", {"server": "fs", "tool": "read"}) == "fs.read"

    def test_tool_name_mcp_empty(self) -> None:
        assert _tool_name_for("mcp_tool_call", {}) == "mcp_tool_call"

    def test_tool_name_unknown(self) -> None:
        assert _tool_name_for("", {}) == "unknown"

    def test_tool_args_command(self) -> None:
        assert _tool_args_for("command_execution", {"command": "ls"}) == {"command": "ls"}

    def test_tool_args_file_change(self) -> None:
        assert _tool_args_for("file_change", {"changes": ["a"]}) == {"changes": ["a"]}

    def test_tool_args_mcp_dict(self) -> None:
        assert _tool_args_for("mcp_tool_call", {"arguments": {"k": "v"}}) == {"k": "v"}

    def test_tool_args_mcp_non_dict(self) -> None:
        assert _tool_args_for("mcp_tool_call", {"arguments": "str"}) == {"value": "str"}

    def test_tool_output_command_success(self) -> None:
        text, is_err = _tool_output_for("command_execution", {"aggregated_output": "hello", "exit_code": 0})
        assert text == "hello"
        assert is_err is False

    def test_tool_output_command_error(self) -> None:
        _, is_err = _tool_output_for("command_execution", {"aggregated_output": "boom", "exit_code": 1})
        assert is_err is True

    def test_tool_output_mcp_error(self) -> None:
        text, is_err = _tool_output_for("mcp_tool_call", {"error": {"message": "not found"}})
        assert "not found" in text
        assert is_err is True

    def test_tool_output_mcp_result(self) -> None:
        text, is_err = _tool_output_for("mcp_tool_call", {"result": {"data": 1}})
        assert json.loads(text) == {"data": 1}
        assert is_err is False

    def test_tool_output_file_change_failed(self) -> None:
        _, is_err = _tool_output_for("file_change", {"status": "failed", "changes": []})
        assert is_err is True

    def test_tool_output_file_change_ok(self) -> None:
        text, is_err = _tool_output_for("file_change", {"status": "ok", "changes": [1, 2]})
        assert "2 changes" in text
        assert is_err is False


# ---------------------------------------------------------------------------
# Text streaming
# ---------------------------------------------------------------------------


class TestTextStreaming:
    async def test_text_start_delta_done(self) -> None:
        events = [
            {"type": "item.started", "item": {"id": "m1", "type": "agent_message", "text": "Hi"}},
            {"type": "item.updated", "item": {"id": "m1", "type": "agent_message", "text": "Hi!"}},
            {"type": "item.completed", "item": {"id": "m1", "type": "agent_message", "text": "Hi! Done"}},
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))

        starts = [e for e in out if isinstance(e, StreamTaskMessageStart)]
        deltas = [e for e in out if isinstance(e, StreamTaskMessageDelta)]
        dones = [e for e in out if isinstance(e, StreamTaskMessageDone)]

        assert len(starts) == 1
        assert isinstance(starts[0].content, TextContent)
        assert len(deltas) >= 1
        all_delta_text = "".join(
            d.delta.text_delta for d in deltas if isinstance(d.delta, TextDelta) and d.delta.text_delta is not None
        )
        assert "Hi" in all_delta_text
        assert len(dones) == 1

    async def test_text_indices_are_monotonic(self) -> None:
        events = [
            {"type": "item.started", "item": {"id": "m1", "type": "agent_message", "text": "A"}},
            {"type": "item.completed", "item": {"id": "m1", "type": "agent_message", "text": "A"}},
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        anchor = [e for e in out if isinstance(e, StreamTaskMessageStart)]
        done = [e for e in out if isinstance(e, StreamTaskMessageDone)]
        assert anchor[0].index == done[0].index

    async def test_empty_text_no_delta(self) -> None:
        events = [
            {"type": "item.started", "item": {"id": "m1", "type": "agent_message", "text": ""}},
            {"type": "item.completed", "item": {"id": "m1", "type": "agent_message", "text": ""}},
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        deltas = [e for e in out if isinstance(e, StreamTaskMessageDelta)]
        assert deltas == []

    async def test_text_author_is_agent(self) -> None:
        events = [
            {"type": "item.started", "item": {"id": "m1", "type": "agent_message", "text": "X"}},
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        for e in out:
            content = getattr(e, "content", None)
            if content and hasattr(content, "author"):
                assert content.author == "agent"


# ---------------------------------------------------------------------------
# Tool call streaming
# ---------------------------------------------------------------------------


class TestToolCallStreaming:
    async def test_command_execution_start_done_full(self) -> None:
        events = [
            {
                "type": "item.started",
                "item": {
                    "id": "t1",
                    "type": "command_execution",
                    "command": "echo hello",
                },
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "t1",
                    "type": "command_execution",
                    "command": "echo hello",
                    "aggregated_output": "hello",
                    "exit_code": 0,
                },
            },
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))

        starts = [e for e in out if isinstance(e, StreamTaskMessageStart)]
        dones = [e for e in out if isinstance(e, StreamTaskMessageDone)]
        fulls = [e for e in out if isinstance(e, StreamTaskMessageFull)]

        assert len(starts) == 1
        assert isinstance(starts[0].content, ToolRequestContent)
        assert starts[0].content.name == "bash"
        assert starts[0].content.arguments == {"command": "echo hello"}
        assert starts[0].content.tool_call_id == "t1"

        assert len(dones) == 1

        assert len(fulls) == 1
        assert isinstance(fulls[0].content, ToolResponseContent)
        resp_content = fulls[0].content.content
        assert isinstance(resp_content, dict)
        assert resp_content["result"] == "hello"
        assert fulls[0].content.tool_call_id == "t1"

    async def test_empty_item_id_request_response_ids_match(self) -> None:
        """A tool with an empty item_id must use the SAME fallback tool_call_id
        on the request (started) and response (completed) halves."""
        events = [
            {"type": "item.started", "item": {"id": "", "type": "command_execution", "command": "ls"}},
            {
                "type": "item.completed",
                "item": {
                    "id": "",
                    "type": "command_execution",
                    "command": "ls",
                    "aggregated_output": ".",
                    "exit_code": 0,
                },
            },
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        # Pull tool_call_id inside the comprehension so the isinstance narrows the
        # content union (the narrowing would not survive a later attribute access).
        req_ids = [
            e.content.tool_call_id
            for e in out
            if isinstance(e, StreamTaskMessageStart) and isinstance(e.content, ToolRequestContent)
        ]
        resp_ids = [
            e.content.tool_call_id
            for e in out
            if isinstance(e, StreamTaskMessageFull) and isinstance(e.content, ToolResponseContent)
        ]
        assert len(req_ids) == 1 and len(resp_ids) == 1
        assert req_ids[0] == resp_ids[0]

    async def test_file_change_synthesizes_start(self) -> None:
        """file_change items may only emit item.completed (no started)."""
        events = [
            {
                "type": "item.completed",
                "item": {
                    "id": "fc1",
                    "type": "file_change",
                    "changes": ["a.py"],
                    "status": "ok",
                },
            }
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        tool_req = [
            e for e in out if isinstance(e, StreamTaskMessageFull) and isinstance(e.content, ToolRequestContent)
        ]
        tool_resp = [
            e for e in out if isinstance(e, StreamTaskMessageFull) and isinstance(e.content, ToolResponseContent)
        ]
        assert len(tool_req) == 1
        assert isinstance(tool_req[0].content, ToolRequestContent)
        assert tool_req[0].content.name == "file_change"
        assert len(tool_resp) == 1

    async def test_mcp_tool_call_name(self) -> None:
        events = [
            {
                "type": "item.started",
                "item": {
                    "id": "mcp1",
                    "type": "mcp_tool_call",
                    "server": "fs",
                    "tool": "read",
                    "arguments": {"path": "/x"},
                },
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "mcp1",
                    "type": "mcp_tool_call",
                    "server": "fs",
                    "tool": "read",
                    "arguments": {"path": "/x"},
                    "result": "content",
                },
            },
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        req = next(
            e for e in out if isinstance(e, StreamTaskMessageStart) and isinstance(e.content, ToolRequestContent)
        )
        assert isinstance(req.content, ToolRequestContent)
        assert req.content.name == "fs.read"

    async def test_tool_error_marks_is_error(self) -> None:
        events = [
            {
                "type": "item.started",
                "item": {"id": "cmd1", "type": "command_execution", "command": "bad"},
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "cmd1",
                    "type": "command_execution",
                    "command": "bad",
                    "aggregated_output": "error output",
                    "exit_code": 127,
                },
            },
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        resp = next(
            e for e in out if isinstance(e, StreamTaskMessageFull) and isinstance(e.content, ToolResponseContent)
        )
        assert isinstance(resp.content, ToolResponseContent)
        resp_body = resp.content.content
        assert isinstance(resp_body, dict)
        assert resp_body.get("is_error") is True

    async def test_tool_indices_request_before_response(self) -> None:
        events = [
            {
                "type": "item.started",
                "item": {"id": "cmd2", "type": "command_execution", "command": "ls"},
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "cmd2",
                    "type": "command_execution",
                    "command": "ls",
                    "aggregated_output": ".",
                    "exit_code": 0,
                },
            },
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        req = next(e for e in out if isinstance(e, StreamTaskMessageStart))
        resp = next(
            e for e in out if isinstance(e, StreamTaskMessageFull) and isinstance(e.content, ToolResponseContent)
        )
        assert req.index is not None and resp.index is not None
        assert req.index < resp.index


# ---------------------------------------------------------------------------
# Reasoning
# ---------------------------------------------------------------------------


class TestReasoningStreaming:
    async def test_reasoning_start_deltas_done(self) -> None:
        """A reasoning block opens with a Start, streams the final text as
        summary + content deltas, and closes with a Done.

        It must NOT emit a Full at the open Start's index: auto_send routes a
        Full into a throwaway streaming context (ignoring the index), which
        would leave the Start context dangling and persist a duplicate, empty
        reasoning message (AGX1 codex reasoning duplicate bug).
        """
        events = [
            {"type": "item.started", "item": {"id": "r1", "type": "reasoning", "text": ""}},
            {
                "type": "item.updated",
                "item": {"id": "r1", "type": "reasoning", "text": "thinking..."},
            },
            {
                "type": "item.completed",
                "item": {"id": "r1", "type": "reasoning", "text": "thinking... done"},
            },
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))

        starts = [e for e in out if isinstance(e, StreamTaskMessageStart)]
        dones = [e for e in out if isinstance(e, StreamTaskMessageDone)]
        reasoning_fulls = [
            e for e in out if isinstance(e, StreamTaskMessageFull) and isinstance(e.content, ReasoningContent)
        ]
        content_deltas = [
            e for e in out if isinstance(e, StreamTaskMessageDelta) and isinstance(e.delta, ReasoningContentDelta)
        ]
        summary_deltas = [
            e for e in out if isinstance(e, StreamTaskMessageDelta) and isinstance(e.delta, ReasoningSummaryDelta)
        ]

        # Exactly one message: Start + deltas + Done, all on the same index, no Full.
        assert len(starts) == 1
        assert isinstance(starts[0].content, ReasoningContent)
        assert reasoning_fulls == []
        assert len(content_deltas) == 1
        content_delta = content_deltas[0].delta
        assert isinstance(content_delta, ReasoningContentDelta)
        assert content_delta.content_delta == "thinking... done"
        assert len(summary_deltas) == 1
        summary_delta = summary_deltas[0].delta
        assert isinstance(summary_delta, ReasoningSummaryDelta)
        assert summary_delta.summary_delta == "thinking... done"
        assert len(dones) == 1
        idx = starts[0].index
        assert content_deltas[0].index == idx
        assert summary_deltas[0].index == idx
        assert dones[0].index == idx

    async def test_reasoning_no_started_opens_and_closes_one_message(self) -> None:
        """If item.completed arrives without item.started, the converter opens a
        Start lazily and closes it with a Done (still one clean message, no Full)."""
        events = [
            {
                "type": "item.completed",
                "item": {"id": "r_orphan", "type": "reasoning", "text": "orphan thought"},
            }
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))

        starts = [e for e in out if isinstance(e, StreamTaskMessageStart)]
        dones = [e for e in out if isinstance(e, StreamTaskMessageDone)]
        reasoning_fulls = [
            e for e in out if isinstance(e, StreamTaskMessageFull) and isinstance(e.content, ReasoningContent)
        ]
        content_deltas = [
            e for e in out if isinstance(e, StreamTaskMessageDelta) and isinstance(e.delta, ReasoningContentDelta)
        ]

        assert len(starts) == 1
        assert isinstance(starts[0].content, ReasoningContent)
        assert reasoning_fulls == []
        assert len(content_deltas) == 1
        content_delta = content_deltas[0].delta
        assert isinstance(content_delta, ReasoningContentDelta)
        assert content_delta.content_delta == "orphan thought"
        assert len(dones) == 1
        assert dones[0].index == starts[0].index

    async def test_reasoning_summary_is_first_line(self) -> None:
        events = [
            {"type": "item.started", "item": {"id": "r2", "type": "reasoning", "text": ""}},
            {
                "type": "item.completed",
                "item": {"id": "r2", "type": "reasoning", "text": "line one\nline two"},
            },
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        summary_event = next(
            e for e in out if isinstance(e, StreamTaskMessageDelta) and isinstance(e.delta, ReasoningSummaryDelta)
        )
        summary_delta = summary_event.delta
        assert isinstance(summary_delta, ReasoningSummaryDelta)
        assert summary_delta.summary_delta == "line one"

    async def test_reasoning_empty_block_closes_with_done_only(self) -> None:
        """A reasoning block that completes with no text still closes its Start."""
        events = [
            {"type": "item.started", "item": {"id": "r3", "type": "reasoning", "text": ""}},
            {"type": "item.completed", "item": {"id": "r3", "type": "reasoning", "text": ""}},
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))

        starts = [e for e in out if isinstance(e, StreamTaskMessageStart)]
        dones = [e for e in out if isinstance(e, StreamTaskMessageDone)]
        deltas = [e for e in out if isinstance(e, StreamTaskMessageDelta)]

        assert len(starts) == 1
        assert deltas == []
        assert len(dones) == 1
        assert dones[0].index == starts[0].index


# ---------------------------------------------------------------------------
# Error events
# ---------------------------------------------------------------------------


class TestErrorEvents:
    async def test_turn_failed_emits_error_text(self) -> None:
        events = [{"type": "turn.failed", "error": {"message": "context length exceeded"}}]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        assert len(out) == 1
        assert isinstance(out[0], StreamTaskMessageFull)
        assert isinstance(out[0].content, TextContent)
        assert "context length exceeded" in out[0].content.content

    async def test_top_level_error_emits_text(self) -> None:
        events = [{"type": "error", "message": "unexpected EOF"}]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        assert len(out) == 1
        assert isinstance(out[0].content, TextContent)
        assert "unexpected EOF" in out[0].content.content

    async def test_item_error_emits_on_completed_only(self) -> None:
        events = [
            {"type": "item.started", "item": {"id": "e1", "type": "error", "message": "bad"}},
            {"type": "item.completed", "item": {"id": "e1", "type": "error", "message": "bad"}},
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        # Only item.completed emits an event for error items
        assert len(out) == 1
        assert isinstance(out[0].content, TextContent)
        assert "bad" in out[0].content.content


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    async def test_empty_stream(self) -> None:
        out = await _collect(convert_codex_to_agentex_events(_aiter([])))
        assert out == []

    async def test_non_json_lines_skipped(self) -> None:
        events: list[str] = ["not json", "also not json"]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        assert out == []

    async def test_blank_lines_skipped(self) -> None:
        out = await _collect(convert_codex_to_agentex_events(_aiter(["", "   ", "\n"])))
        assert out == []

    async def test_pre_decoded_dict_events(self) -> None:
        """Events passed as dicts (pre-decoded) should work without JSON parsing."""
        events: list[dict[str, Any]] = [
            {"type": "item.started", "item": {"id": "m1", "type": "agent_message", "text": "hi"}},
            {
                "type": "item.completed",
                "item": {"id": "m1", "type": "agent_message", "text": "hi"},
            },
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        assert len(out) > 0

    async def test_thread_started_no_message(self) -> None:
        events = [{"type": "thread.started", "thread_id": "t1"}]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        assert out == []

    async def test_turn_started_no_message(self) -> None:
        out = await _collect(convert_codex_to_agentex_events(_aiter([{"type": "turn.started"}])))
        assert out == []

    async def test_turn_completed_no_message(self) -> None:
        out = await _collect(
            convert_codex_to_agentex_events(_aiter([{"type": "turn.completed", "usage": {"input_tokens": 1}}]))
        )
        assert out == []

    async def test_unknown_event_type_no_message(self) -> None:
        out = await _collect(convert_codex_to_agentex_events(_aiter([{"type": "some.future.event"}])))
        assert out == []

    async def test_unknown_item_type_no_message(self) -> None:
        out = await _collect(
            convert_codex_to_agentex_events(
                _aiter([{"type": "item.started", "item": {"id": "x", "type": "future_item"}}])
            )
        )
        assert out == []


# ---------------------------------------------------------------------------
# on_result callback
# ---------------------------------------------------------------------------


class TestOnResult:
    async def test_session_id_captured(self) -> None:
        result: dict[str, Any] = {}

        def on_result(r: dict[str, Any]) -> None:
            result.update(r)

        events = [
            {"type": "thread.started", "thread_id": "sess-xyz"},
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
            },
        ]
        await _collect(convert_codex_to_agentex_events(_aiter(events), on_result=on_result))
        assert result["session_id"] == "sess-xyz"

    async def test_usage_forwarded(self) -> None:
        result: dict[str, Any] = {}

        def on_result(r: dict[str, Any]) -> None:
            result.update(r)

        events = [
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            }
        ]
        await _collect(convert_codex_to_agentex_events(_aiter(events), on_result=on_result))
        assert result["usage"] == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}

    async def test_tool_count(self) -> None:
        result: dict[str, Any] = {}

        def on_result(r: dict[str, Any]) -> None:
            result.update(r)

        events = [
            {
                "type": "item.started",
                "item": {"id": "t1", "type": "command_execution", "command": "ls"},
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "t1",
                    "type": "command_execution",
                    "command": "ls",
                    "aggregated_output": ".",
                    "exit_code": 0,
                },
            },
            {"type": "turn.completed", "usage": None},
        ]
        await _collect(convert_codex_to_agentex_events(_aiter(events), on_result=on_result))
        assert result["tool_call_count"] == 1

    async def test_no_callback_when_none(self) -> None:
        """Passing on_result=None should not raise."""
        events = [{"type": "turn.completed", "usage": None}]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events), on_result=None))
        assert out == []

    async def test_on_result_called_even_without_turn_completed(self) -> None:
        """on_result fires at end of stream even if turn.completed never arrived."""
        result: dict[str, Any] = {}

        def on_result(r: dict[str, Any]) -> None:
            result.update(r)

        events: list[Any] = []
        await _collect(convert_codex_to_agentex_events(_aiter(events), on_result=on_result))
        assert result.get("usage") is None
        assert result.get("session_id") is None


# ---------------------------------------------------------------------------
# Multi-step turn: tool → text
# ---------------------------------------------------------------------------


class TestMultiStepTurn:
    async def test_tool_then_text_monotonic_indices(self) -> None:
        events = [
            {
                "type": "item.started",
                "item": {"id": "cmd1", "type": "command_execution", "command": "ls"},
            },
            {
                "type": "item.completed",
                "item": {
                    "id": "cmd1",
                    "type": "command_execution",
                    "command": "ls",
                    "aggregated_output": "file.txt",
                    "exit_code": 0,
                },
            },
            {
                "type": "item.started",
                "item": {"id": "msg1", "type": "agent_message", "text": ""},
            },
            {
                "type": "item.completed",
                "item": {"id": "msg1", "type": "agent_message", "text": "Done"},
            },
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        indices = [e.index for e in out]
        assert indices == sorted(indices), "indices must be monotonically non-decreasing"

    async def test_two_text_blocks_distinct_indices(self) -> None:
        events = [
            {
                "type": "item.started",
                "item": {"id": "a", "type": "agent_message", "text": "first"},
            },
            {"type": "item.completed", "item": {"id": "a", "type": "agent_message", "text": "first"}},
            {
                "type": "item.started",
                "item": {"id": "b", "type": "agent_message", "text": "second"},
            },
            {"type": "item.completed", "item": {"id": "b", "type": "agent_message", "text": "second"}},
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(events)))
        starts = [e for e in out if isinstance(e, StreamTaskMessageStart)]
        assert len(starts) == 2
        assert starts[0].index != starts[1].index

    async def test_json_string_events(self) -> None:
        """Events may arrive as raw newline-delimited JSON strings."""
        raw_events = [
            json.dumps({"type": "item.started", "item": {"id": "s1", "type": "agent_message", "text": "hello"}}),
            json.dumps({"type": "item.completed", "item": {"id": "s1", "type": "agent_message", "text": "hello"}}),
        ]
        out = await _collect(convert_codex_to_agentex_events(_aiter(raw_events)))
        assert len(out) > 0
        assert any(isinstance(e, StreamTaskMessageStart) for e in out)
