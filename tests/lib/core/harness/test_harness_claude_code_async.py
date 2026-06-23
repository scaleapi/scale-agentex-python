"""Integration test: async (Redis-streaming) channel with a claude-code turn.

Exercises the unified harness surface (UnifiedEmitter.auto_send_turn + ClaudeCodeTurn)
with hand-built claude-code ``stream-json`` envelopes and a fake streaming
backend so the test runs fully offline (no claude-code CLI subprocess, no
Redis, no Agentex server).

Native envelope shapes are copied verbatim from the claude-code turn test and
conformance fixtures (assistant tool_use -> Start(ToolRequestContent)+Done;
user tool_result -> Full(ToolResponseContent); assistant text ->
Start(TextContent)+Delta+Done; result envelope -> usage).

What is tested
--------------
- auto_send pushes the correct message contexts: tool_request + tool_response
  + text (in that order).
- TurnResult.final_text equals the final assistant text.
- TurnResult.usage reflects the claude-code ``result`` envelope (input/output
  tokens, cost, num_llm_calls from num_turns).
- With a SpanTracer + fake tracing, a tool span is derived on the async path.

What is NOT covered without live infrastructure
-----------------------------------------------
- Actual Redis streaming.
- The ACP on_task_event_send / on_task_create / on_task_cancel lifecycle.
- A real claude-code CLI subprocess / live model behaviour.

See also: test_harness_claude_code_sync.py and test_harness_claude_code_temporal.py.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from agentex.types.task_message import TaskMessage
from tests.lib.core.harness._fakes import FakeTracing
from agentex.lib.core.harness.types import TurnResult
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._claude_code_turn import ClaudeCodeTurn

# ---------------------------------------------------------------------------
# Native claude-code envelope fixtures
# ---------------------------------------------------------------------------


def _tool_then_text_envelopes() -> list[dict[str, Any]]:
    return [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_read",
                        "name": "Read",
                        "input": {"path": "/workspace/README.md"},
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
                        "tool_use_id": "call_read",
                        "content": "# My Project — temperature 72F",
                    }
                ]
            },
        },
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "The project file says 72F."}]},
        },
        {
            "type": "result",
            "usage": {"input_tokens": 200, "output_tokens": 80},
            "cost_usd": 0.015,
            "num_turns": 2,
        },
    ]


async def _aiter(envelopes: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for e in envelopes:
        yield e


# ---------------------------------------------------------------------------
# Fake streaming backend
# ---------------------------------------------------------------------------


class _FakeCtx:
    def __init__(self, sink: list[Any], ctype: str, initial_content: Any) -> None:
        self.sink = sink
        self.ctype = ctype
        self.task_message = TaskMessage(id="msg-1", task_id="task1", content=initial_content)

    async def __aenter__(self) -> "_FakeCtx":
        self.sink.append(("open", self.ctype, self.task_message.content))
        return self

    async def __aexit__(self, *args: Any) -> bool:
        await self.close()
        return False

    async def close(self) -> None:
        self.sink.append(("close", self.ctype))

    async def stream_update(self, update: Any) -> Any:
        self.sink.append(("delta", self.ctype, update))
        return update


class _FakeStreaming:
    def __init__(self) -> None:
        self.sink: list[Any] = []
        self.messages_opened: list[Any] = []

    def streaming_task_message_context(
        self,
        task_id: str,
        initial_content: Any,
        streaming_mode: str = "coalesced",
        created_at: Any = None,
    ) -> _FakeCtx:
        ctype = getattr(initial_content, "type", None) or ""
        self.messages_opened.append(initial_content)
        return _FakeCtx(self.sink, ctype, initial_content)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_auto_send_turn(
    envelopes: list[dict[str, Any]],
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    fake_tracing: FakeTracing | None = None,
) -> tuple[TurnResult, _FakeStreaming]:
    fake_streaming = _FakeStreaming()
    tracer: SpanTracer | bool | None = None
    if trace_id and fake_tracing is not None:
        tracer = SpanTracer(
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            task_id="task1",
            tracing=fake_tracing,
        )

    turn = ClaudeCodeTurn(_aiter(envelopes))
    emitter = UnifiedEmitter(
        task_id="task1",
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        tracer=tracer if tracer is not None else False,
        streaming=fake_streaming,
    )
    result = await emitter.auto_send_turn(turn)
    return result, fake_streaming


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAsyncAutoSendMessageOrder:
    async def test_tool_request_pushed_before_tool_response(self) -> None:
        _, fake_streaming = await _run_auto_send_turn(_tool_then_text_envelopes())
        types = [getattr(m, "type", None) for m in fake_streaming.messages_opened]
        assert "tool_request" in types
        assert "tool_response" in types
        assert types.index("tool_request") < types.index("tool_response")

    async def test_text_pushed_last(self) -> None:
        _, fake_streaming = await _run_auto_send_turn(_tool_then_text_envelopes())
        types = [getattr(m, "type", None) for m in fake_streaming.messages_opened]
        assert types[-1] == "text", f"Expected last type=text, got {types}"


class TestAsyncAutoSendContent:
    async def test_tool_request_content(self) -> None:
        _, fake_streaming = await _run_auto_send_turn(_tool_then_text_envelopes())
        tool_reqs = [m for m in fake_streaming.messages_opened if isinstance(m, ToolRequestContent)]
        assert len(tool_reqs) == 1
        assert tool_reqs[0].name == "Read"

    async def test_tool_response_content(self) -> None:
        _, fake_streaming = await _run_auto_send_turn(_tool_then_text_envelopes())
        tool_resps = [m for m in fake_streaming.messages_opened if isinstance(m, ToolResponseContent)]
        assert len(tool_resps) == 1
        assert "72F" in str(tool_resps[0].content)

    async def test_tool_call_ids_match(self) -> None:
        _, fake_streaming = await _run_auto_send_turn(_tool_then_text_envelopes())
        tool_req = next(m for m in fake_streaming.messages_opened if isinstance(m, ToolRequestContent))
        tool_resp = next(m for m in fake_streaming.messages_opened if isinstance(m, ToolResponseContent))
        assert tool_req.tool_call_id == tool_resp.tool_call_id == "call_read"


class TestAsyncAutoSendFinalTextAndUsage:
    async def test_final_text_matches_last_text(self) -> None:
        result, _ = await _run_auto_send_turn(_tool_then_text_envelopes())
        assert result.final_text == "The project file says 72F."

    async def test_usage_from_result_envelope(self) -> None:
        """TurnResult.usage reflects the claude-code result envelope."""
        result, _ = await _run_auto_send_turn(_tool_then_text_envelopes())
        assert result.usage is not None
        assert result.usage.input_tokens == 200
        assert result.usage.output_tokens == 80
        assert result.usage.total_tokens == 280
        assert result.usage.cost_usd == pytest.approx(0.015)
        assert result.usage.num_llm_calls == 2

    async def test_context_lifecycle_open_then_close(self) -> None:
        _, fake_streaming = await _run_auto_send_turn(_tool_then_text_envelopes())
        opens = [e for e in fake_streaming.sink if e[0] == "open"]
        closes = [e for e in fake_streaming.sink if e[0] == "close"]
        assert len(opens) == len(closes)
        assert len(opens) == len(fake_streaming.messages_opened)


class TestAsyncAutoSendSpanDerivation:
    async def test_tool_span_derived_on_async_path(self) -> None:
        fake_tracing = FakeTracing()
        await _run_auto_send_turn(
            _tool_then_text_envelopes(),
            trace_id="trace1",
            parent_span_id="parent",
            fake_tracing=fake_tracing,
        )
        assert len(fake_tracing.started) == 1
        assert fake_tracing.started[0][0] == "Read"
        assert len(fake_tracing.ended) == 1
        assert "72F" in str(fake_tracing.ended[0][1])
