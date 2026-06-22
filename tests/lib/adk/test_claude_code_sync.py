"""Tests for the claude-code stream-json -> Agentex StreamTaskMessage* converter."""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from agentex.types.text_content import TextContent
from agentex.types.reasoning_content import ReasoningContent
from agentex.types.task_message_delta import TextDelta
from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.types.reasoning_content_delta import ReasoningContentDelta
from agentex.lib.adk._modules._claude_code_sync import convert_claude_code_to_agentex_events


async def _aiter(events: list[Any]) -> AsyncIterator[Any]:
    for e in events:
        yield e


async def _collect(stream: AsyncIterator[Any]) -> list[Any]:
    return [e async for e in stream]


# ---------------------------------------------------------------------------
# Text content
# ---------------------------------------------------------------------------


class TestTextContent:
    async def test_text_block_in_assistant_message_emits_start_delta_done(self):
        envelopes = [
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Hello world"}]},
            }
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))

        assert len(out) == 3
        assert isinstance(out[0], StreamTaskMessageStart)
        assert isinstance(out[0].content, TextContent)
        assert out[0].content.content == ""
        assert isinstance(out[1], StreamTaskMessageDelta)
        assert isinstance(out[1].delta, TextDelta)
        assert out[1].delta.text_delta == "Hello world"
        assert isinstance(out[2], StreamTaskMessageDone)
        assert out[0].index == out[1].index == out[2].index

    async def test_empty_text_block_is_skipped(self):
        envelopes = [
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": ""}]},
            }
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))
        assert out == []

    async def test_streamed_text_via_stream_event_emits_start_deltas_done(self):
        envelopes = [
            {
                "type": "stream_event",
                "event": {"type": "content_block_start", "index": 0, "content_block": {"type": "text"}},
            },
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "Hello"},
                },
            },
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": " world"},
                },
            },
            {
                "type": "stream_event",
                "event": {"type": "content_block_stop", "index": 0},
            },
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))

        starts = [e for e in out if isinstance(e, StreamTaskMessageStart)]
        deltas = [e for e in out if isinstance(e, StreamTaskMessageDelta)]
        dones = [e for e in out if isinstance(e, StreamTaskMessageDone)]

        assert len(starts) == 1
        assert isinstance(starts[0].content, TextContent)
        assert len(deltas) == 2
        assert isinstance(deltas[0].delta, TextDelta)
        assert deltas[0].delta.text_delta == "Hello"
        assert isinstance(deltas[1].delta, TextDelta)
        assert deltas[1].delta.text_delta == " world"
        assert len(dones) == 1

    async def test_streamed_text_not_re_emitted_by_assistant_block(self):
        """After stream_event triple, the final assistant block must not re-emit the text."""
        envelopes = [
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text"},
                },
            },
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "streamed"},
                },
            },
            {
                "type": "stream_event",
                "event": {"type": "content_block_stop", "index": 0},
            },
            # Final assistant message with same text — must NOT be re-emitted
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "streamed"}]},
            },
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))
        text_starts = [e for e in out if isinstance(e, StreamTaskMessageStart) and isinstance(e.content, TextContent)]
        assert len(text_starts) == 1, "Text block must not be emitted twice"

    async def test_later_turn_non_streamed_text_not_dropped(self):
        """A non-streamed text block in a later turn must not be dropped because an
        earlier turn streamed a block at the same index."""
        envelopes = [
            # Turn 1: streamed text at index 0 (dedup'd against the materialised msg).
            {
                "type": "stream_event",
                "event": {"type": "content_block_start", "index": 0, "content_block": {"type": "text"}},
            },
            {
                "type": "stream_event",
                "event": {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "first"}},
            },
            {"type": "stream_event", "event": {"type": "content_block_stop", "index": 0}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "first"}]}},
            # Turn 2: a NON-streamed text block, also at index 0.
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "second"}]}},
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))
        deltas = [
            e.delta.text_delta for e in out if isinstance(e, StreamTaskMessageDelta) and isinstance(e.delta, TextDelta)
        ]
        assert deltas == ["first", "second"], "Later turn's non-streamed text must still be delivered"


# ---------------------------------------------------------------------------
# Thinking / reasoning content
# ---------------------------------------------------------------------------


class TestThinkingContent:
    async def test_thinking_block_emits_reasoning_start_delta_done(self):
        envelopes = [
            {
                "type": "assistant",
                "message": {"content": [{"type": "thinking", "thinking": "Let me reason..."}]},
            }
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))

        assert len(out) == 3
        assert isinstance(out[0], StreamTaskMessageStart)
        assert isinstance(out[0].content, ReasoningContent)
        # Summary must be populated from the thinking text
        assert out[0].content.summary == ["Let me reason..."]
        assert isinstance(out[1], StreamTaskMessageDelta)
        assert isinstance(out[1].delta, ReasoningContentDelta)
        assert out[1].delta.content_delta == "Let me reason..."
        assert out[1].delta.content_index == 0
        assert isinstance(out[2], StreamTaskMessageDone)

    async def test_empty_thinking_block_is_skipped(self):
        envelopes = [
            {
                "type": "assistant",
                "message": {"content": [{"type": "thinking", "thinking": ""}]},
            }
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))
        assert out == []

    async def test_streamed_thinking_emits_reasoning_start_deltas_done(self):
        envelopes = [
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "thinking"},
                },
            },
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "thinking_delta", "thinking": "step one"},
                },
            },
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "thinking_delta", "thinking": " step two"},
                },
            },
            {
                "type": "stream_event",
                "event": {"type": "content_block_stop", "index": 0},
            },
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))

        starts = [e for e in out if isinstance(e, StreamTaskMessageStart)]
        deltas = [e for e in out if isinstance(e, StreamTaskMessageDelta)]
        dones = [e for e in out if isinstance(e, StreamTaskMessageDone)]

        assert len(starts) == 1
        assert isinstance(starts[0].content, ReasoningContent)
        assert len(deltas) == 2
        assert isinstance(deltas[0].delta, ReasoningContentDelta)
        assert deltas[0].delta.content_delta == "step one"
        assert isinstance(deltas[1].delta, ReasoningContentDelta)
        assert deltas[1].delta.content_delta == " step two"
        assert len(dones) == 1

    async def test_thinking_block_start_with_no_deltas_allows_assistant_to_fill(self):
        """A thinking block_start without any deltas leaves the final assistant block
        free to emit the thinking text (the block index is not claimed as streamed)."""
        envelopes = [
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "thinking"},
                },
            },
            # No thinking_delta — close block immediately
            {
                "type": "stream_event",
                "event": {"type": "content_block_stop", "index": 0},
            },
            # Final assistant message has the thinking text
            {
                "type": "assistant",
                "message": {"content": [{"type": "thinking", "thinking": "delayed thinking"}]},
            },
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))
        # The assistant block should produce a full thinking message (Start+Delta+Done)
        reasoning_starts = [
            e for e in out if isinstance(e, StreamTaskMessageStart) and isinstance(e.content, ReasoningContent)
        ]
        # There will be the empty start from stream_event, plus the one from assistant block
        reasoning_deltas = [
            e for e in out if isinstance(e, StreamTaskMessageDelta) and isinstance(e.delta, ReasoningContentDelta)
        ]
        assert len(reasoning_deltas) >= 1
        assert any(
            isinstance(d.delta, ReasoningContentDelta) and d.delta.content_delta == "delayed thinking"
            for d in reasoning_deltas
        )


# ---------------------------------------------------------------------------
# Tool calls and results
# ---------------------------------------------------------------------------


class TestToolCallsAndResults:
    async def test_tool_use_block_emits_start_done(self):
        envelopes = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call_abc",
                            "name": "Bash",
                            "input": {"command": "ls /"},
                        }
                    ]
                },
            }
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))

        assert len(out) == 2
        assert isinstance(out[0], StreamTaskMessageStart)
        assert isinstance(out[0].content, ToolRequestContent)
        assert out[0].content.tool_call_id == "call_abc"
        assert out[0].content.name == "Bash"
        assert out[0].content.arguments == {"command": "ls /"}
        assert isinstance(out[1], StreamTaskMessageDone)

    async def test_tool_result_block_emits_full(self):
        envelopes = [
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_abc",
                            "content": "file1.txt\nfile2.txt",
                        }
                    ]
                },
            }
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))

        assert len(out) == 1
        assert isinstance(out[0], StreamTaskMessageFull)
        assert isinstance(out[0].content, ToolResponseContent)
        assert out[0].content.tool_call_id == "call_abc"
        assert "file1.txt" in str(out[0].content.content)

    async def test_tool_result_list_content_joined(self):
        envelopes = [
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tid",
                            "content": [
                                {"type": "text", "text": "line1"},
                                {"type": "text", "text": "line2"},
                            ],
                        }
                    ]
                },
            }
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))
        assert isinstance(out[0], StreamTaskMessageFull)
        assert isinstance(out[0].content, ToolResponseContent)
        payload = str(out[0].content.content)
        assert "line1" in payload
        assert "line2" in payload

    async def test_tool_result_error_flag_passed_through(self):
        envelopes = [
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "err_call",
                            "content": "Permission denied",
                            "is_error": True,
                        }
                    ]
                },
            }
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))
        assert isinstance(out[0], StreamTaskMessageFull)
        assert isinstance(out[0].content, ToolResponseContent)
        assert isinstance(out[0].content.content, dict)
        assert out[0].content.content.get("is_error") is True

    async def test_tool_result_truncation(self):
        long_result = "x" * 5000
        envelopes = [
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "t",
                            "content": long_result,
                        }
                    ]
                },
            }
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))
        result_str = out[0].content.content.get("result", "")
        assert len(result_str) <= 4000


# ---------------------------------------------------------------------------
# on_result callback
# ---------------------------------------------------------------------------


class TestOnResult:
    async def test_on_result_called_with_result_envelope(self):
        captured: list[dict] = []

        async def capture(envelope):
            captured.append(envelope)

        envelopes = [
            {
                "type": "result",
                "session_id": "sess123",
                "cost_usd": 0.012,
                "usage": {"input_tokens": 100, "output_tokens": 50},
            }
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes), on_result=capture))

        # result envelope does not emit any StreamTaskMessage
        assert out == []
        assert len(captured) == 1
        assert captured[0]["session_id"] == "sess123"
        assert captured[0]["cost_usd"] == pytest.approx(0.012)

    async def test_on_result_not_called_when_no_result_envelope(self):
        captured: list[dict] = []

        async def capture(envelope):
            captured.append(envelope)

        envelopes = [
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Hi"}]},
            }
        ]
        await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes), on_result=capture))
        assert captured == []

    async def test_no_on_result_does_not_raise(self):
        envelopes = [
            {
                "type": "result",
                "cost_usd": 0.001,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        ]
        # Should not raise even without a callback
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))
        assert out == []


# ---------------------------------------------------------------------------
# Message indexing
# ---------------------------------------------------------------------------


class TestMessageIndexing:
    async def test_multiple_blocks_get_distinct_indices(self):
        envelopes = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "First"},
                        {
                            "type": "tool_use",
                            "id": "c1",
                            "name": "Read",
                            "input": {"path": "/tmp"},
                        },
                    ]
                },
            },
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "c1",
                            "content": "some content",
                        }
                    ]
                },
            },
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Done"}]},
            },
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))

        # Gather all Start/Full events and check indices are monotonically increasing
        anchors = [e for e in out if isinstance(e, (StreamTaskMessageStart, StreamTaskMessageFull))]
        indices = [e.index for e in anchors]
        assert indices == sorted(indices), "Indices must be monotonically increasing"
        assert len(set(indices)) == len(indices), "All indices must be distinct"

    async def test_system_init_and_unknown_envelopes_produce_no_output(self):
        envelopes = [
            {"type": "system", "subtype": "init", "session_id": "sess"},
            {"type": "unknown_future_type", "data": "whatever"},
        ]
        out = await _collect(convert_claude_code_to_agentex_events(_aiter(envelopes)))
        assert out == []

    async def test_non_json_string_lines_are_skipped(self):
        lines = [
            "not json at all",
            '{"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}}',
        ]

        async def _str_iter():
            for line in lines:
                yield line

        out = await _collect(convert_claude_code_to_agentex_events(_str_iter()))
        assert len(out) == 3  # Start + Delta + Done for the text block

    async def test_empty_lines_are_skipped(self):
        lines = ["", "  ", '{"type": "system", "subtype": "init"}']

        async def _str_iter():
            for line in lines:
                yield line

        out = await _collect(convert_claude_code_to_agentex_events(_str_iter()))
        assert out == []


# ---------------------------------------------------------------------------
# Author
# ---------------------------------------------------------------------------


class TestContentAuthors:
    @pytest.mark.parametrize(
        "envelope",
        [
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "hi"}]},
            },
            {
                "type": "assistant",
                "message": {"content": [{"type": "thinking", "thinking": "thoughts"}]},
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "c",
                            "name": "t",
                            "input": {},
                        }
                    ]
                },
            },
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "c",
                            "content": "ok",
                        }
                    ]
                },
            },
        ],
    )
    async def test_all_content_authored_by_agent(self, envelope: dict):
        out = await _collect(convert_claude_code_to_agentex_events(_aiter([envelope])))
        for e in out:
            content = getattr(e, "content", None)
            if content is not None and hasattr(content, "author"):
                assert content.author == "agent"
