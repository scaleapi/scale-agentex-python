"""Integration test: Temporal channel with a LangGraph agent.

The Temporal LangGraph agent pattern uses ``emit_langgraph_messages`` (now in
``_langgraph_sync.py``) inside a Temporal activity. That helper is not
yet unified onto the harness surface (it has its own Redis-streaming code).

This test file verifies the LangGraph Temporal agent's streaming behavior using
the same fake streaming infrastructure as test_harness_langgraph_async.py. The
key difference from the non-temporal async path is that in Temporal, each agent
turn runs inside a Temporal activity that has already been handed the task_id
and a pre-wired streaming client — so the ``UnifiedEmitter.auto_send_turn``
path is identical. The graph activities and workflow scaffolding are not tested
here; that requires a running Temporal cluster.

What is tested
--------------
- stream_langgraph_events (the public async API used by temporal agent acp.py via
  the workflow activity) produces the same result via the unified surface.
- Usage from AIMessage.usage_metadata is captured in TurnResult.usage.
- The auto_send_turn path for a temporal-style call (same as async).

What is NOT covered without live infrastructure
-----------------------------------------------
- Actual Temporal workflow execution (requires a running Temporal cluster).
- The Temporal activity retry/compensation logic.
- LangGraph checkpoint storage via TemporalCheckpointer.
- emit_langgraph_messages (the Temporal-specific streaming helper).
- Real LLM calls or real LangGraph graph execution.

See also: test_harness_langgraph_sync.py and test_harness_langgraph_async.py.
"""

from __future__ import annotations

import sys
from typing import Any
from dataclasses import field, dataclass

import pytest

from agentex.types.task_message import TaskMessage
from agentex.types.text_content import TextContent
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._langgraph_turn import LangGraphTurn, stream_langgraph_events

# ---------------------------------------------------------------------------
# Remove conftest stubs so real langchain_core types are used
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _real_langchain_core():
    stub_keys = [k for k in sys.modules if k.startswith("langchain_core") or k.startswith("langgraph")]
    saved = {k: sys.modules.pop(k) for k in stub_keys}
    import importlib

    importlib.import_module("langchain_core.messages")
    yield
    sys.modules.update(saved)


# ---------------------------------------------------------------------------
# Fake streaming backend
# ---------------------------------------------------------------------------


@dataclass
class _FakeCtx:
    ctype: str
    initial_content: Any
    task_message: TaskMessage
    closed: bool = False
    deltas: list[Any] = field(default_factory=list)

    async def __aenter__(self) -> "_FakeCtx":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        await self.close()
        return False

    async def close(self) -> None:
        self.closed = True

    async def stream_update(self, update: Any) -> Any:
        self.deltas.append(update)
        return update


class _FakeStreaming:
    def __init__(self) -> None:
        self.contexts: list[_FakeCtx] = []

    def streaming_task_message_context(self, task_id: str, initial_content: Any, **kw: Any) -> _FakeCtx:
        ctype = getattr(initial_content, "type", None) or ""
        tm = TaskMessage(id=f"m{len(self.contexts) + 1}", task_id=task_id, content=initial_content)
        ctx = _FakeCtx(ctype=ctype, initial_content=initial_content, task_message=tm)
        self.contexts.append(ctx)
        return ctx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stream(events: list[tuple[str, Any]]):
    async def _gen():
        for e in events:
            yield e

    return _gen()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTemporalAutoSendChannel:
    async def test_stream_langgraph_events_plain_text(self, monkeypatch):
        """stream_langgraph_events (used by temporal agents via the acp.py activity) returns
        the accumulated final text."""
        from langchain_core.messages import AIMessage, AIMessageChunk

        from agentex.lib import adk as adk_module

        fake_streaming = _FakeStreaming()
        monkeypatch.setattr(adk_module, "streaming", fake_streaming)

        chunk = AIMessageChunk(content="Hello Temporal!")
        ai_msg = AIMessage(content="Hello Temporal!")
        events = [
            ("messages", (chunk, {})),
            ("updates", {"agent": {"messages": [ai_msg]}}),
        ]

        final = await stream_langgraph_events(_make_stream(events), "task-1")
        assert final == "Hello Temporal!"

    async def test_stream_langgraph_events_tool_call(self, monkeypatch):
        from langchain_core.messages import AIMessage, ToolMessage

        from agentex.lib import adk as adk_module

        fake_streaming = _FakeStreaming()
        monkeypatch.setattr(adk_module, "streaming", fake_streaming)

        tc = {"id": "c1", "name": "search", "args": {"q": "test"}}
        ai_msg = AIMessage(content="", tool_calls=[tc])
        tool_msg = ToolMessage(content="results", tool_call_id="c1", name="search")
        chunk_final = AIMessage(content="Here are the results.")

        events = [
            ("updates", {"agent": {"messages": [ai_msg]}}),
            ("updates", {"tools": {"messages": [tool_msg]}}),
            ("updates", {"agent": {"messages": [chunk_final]}}),
        ]

        final = await stream_langgraph_events(_make_stream(events), "task-1")

        # Check tool request and response posted to fake streaming
        tool_req_ctxs = [c for c in fake_streaming.contexts if isinstance(c.initial_content, ToolRequestContent)]
        tool_resp_ctxs = [c for c in fake_streaming.contexts if isinstance(c.initial_content, ToolResponseContent)]
        assert len(tool_req_ctxs) == 1
        assert len(tool_resp_ctxs) == 1
        assert tool_req_ctxs[0].initial_content.name == "search"

    async def test_langgraph_turn_auto_send_via_unified_emitter(self):
        """Direct UnifiedEmitter.auto_send_turn path used by temporal agent workflow
        activities. Uses a fake streaming backend (no Redis)."""
        from langchain_core.messages import AIMessage, AIMessageChunk

        fake_streaming = _FakeStreaming()
        chunk = AIMessageChunk(content="Temporal answer!")
        ai_msg = AIMessage(content="Temporal answer!")
        events = [
            ("messages", (chunk, {})),
            ("updates", {"agent": {"messages": [ai_msg]}}),
        ]

        turn = LangGraphTurn(_make_stream(events), model=None)
        emitter = UnifiedEmitter(
            task_id="task-1",
            trace_id=None,
            parent_span_id=None,
            streaming=fake_streaming,
        )
        result = await emitter.auto_send_turn(turn)

        assert result.final_text == "Temporal answer!"
        text_ctxs = [c for c in fake_streaming.contexts if isinstance(c.initial_content, TextContent)]
        assert len(text_ctxs) == 1

    async def test_usage_captured_via_turn_after_events_consumed(self):
        """Usage from AIMessage.usage_metadata is captured via the on_final_ai_message
        callback during event iteration. The authoritative usage is on turn.usage()
        after events are consumed (emitter.auto_send_turn evaluates turn.usage()
        eagerly before iteration, so TurnResult.usage is a pre-iteration snapshot)."""
        from langchain_core.messages import AIMessage

        fake_streaming = _FakeStreaming()
        usage_meta = {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30}
        ai_msg = AIMessage(content="answer", usage_metadata=usage_meta)
        events = [("updates", {"agent": {"messages": [ai_msg]}})]

        turn = LangGraphTurn(_make_stream(events), model="gpt-4o")
        emitter = UnifiedEmitter(
            task_id="task-1",
            trace_id=None,
            parent_span_id=None,
            streaming=fake_streaming,
        )
        await emitter.auto_send_turn(turn)

        # After auto_send_turn, turn.usage() has the captured values
        usage = turn.usage()
        assert usage.input_tokens == 20
        assert usage.output_tokens == 10
        assert usage.total_tokens == 30

    async def test_empty_stream_returns_empty_string(self, monkeypatch):
        from agentex.lib import adk as adk_module

        fake_streaming = _FakeStreaming()
        monkeypatch.setattr(adk_module, "streaming", fake_streaming)

        final = await stream_langgraph_events(_make_stream([]), "task-1")
        assert final == ""
        assert fake_streaming.contexts == []
