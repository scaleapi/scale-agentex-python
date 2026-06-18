"""Integration test: Temporal-backed pydantic-ai agent, offline.

Exercises the core of the Temporal pydantic-ai harness path — the
event_stream_handler activity — with a TemporalAgent backed by TestModel so the
test runs fully offline (no Temporal server, no Redis, no API keys).

Architecture overview
---------------------
In a real Temporal deployment the pydantic-ai Temporal harness runs like this:

    HTTP POST /task/event/send
        -> @workflow.signal on At110PydanticAiWorkflow
        -> temporal_agent.run(user_message, deps=TaskDeps(...))
            internally schedules:
            1. request_activity (LLM HTTP call — recorded by Temporal)
            2. call_tool_activity (for each tool call — also recorded)
            3. event_stream_handler_activity (streams events to Redis)

The third activity is what we test here: it receives a
``RunContext[TaskDeps]`` and an ``AsyncIterable[AgentStreamEvent]`` from
pydantic-ai, calls ``stream_pydantic_ai_events`` (which internally constructs
a ``UnifiedEmitter`` + ``PydanticAITurn`` and calls ``auto_send_turn``), and
pushes the resulting messages to Redis.

What we test
-----------
Since ``TemporalAgent.run_stream_events`` works offline with TestModel (it does
not schedule Temporal activities — it runs in-process), we can:

1. Build a TemporalAgent with TestModel.
2. Call ``run_stream_events`` on it directly, just as the event_stream_handler
   would see the event iterable.
3. Feed that stream into ``stream_pydantic_ai_events`` backed by a fake streaming
   backend, and assert the canonical message sequence.

This covers the full inner harness chain that the Temporal workflow exercises,
minus the Temporal scheduling/durability layer itself.

What is NOT covered without live infrastructure
-----------------------------------------------
- Temporal scheduling (the workflow.signal -> activity dispatch chain).
- Temporal durability guarantees and replay behaviour.
- Redis streaming (requires a running Redis instance).
- Multi-turn history (pydantic-ai message_history round-tripping via Temporal
  workflow state).
- Real LLM calls or production model behaviour.
- The full temporal_agent.run(...) path, which schedules activities and cannot
  run without a connected Temporal client.

To test with live infrastructure: spin up Temporal + Redis + the ACP server +
the Temporal worker, then use the AsyncAgentex client to create a task, send a
message, and poll for messages — exactly as the existing examples/tutorials/
10_async/10_temporal/110_pydantic_ai/tests/test_agent.py does.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai.durable_exec.temporal import TemporalAgent

from agentex.types.task_message import TaskMessage
from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.types.tool_request_content import ToolRequestContent
from agentex.types.tool_response_content import ToolResponseContent
from agentex.lib.adk._modules._pydantic_ai_turn import PydanticAITurn

# ---------------------------------------------------------------------------
# Agent under test (mirrors examples/tutorials/10_async/10_temporal/110_pydantic_ai)
# ---------------------------------------------------------------------------


class TaskDeps(BaseModel):
    """Per-run dependencies injected via RunContext.deps."""

    task_id: str
    parent_span_id: str | None = None


def _make_temporal_agent() -> TemporalAgent[TaskDeps, str]:
    """Build a TemporalAgent with TestModel and one weather tool.

    The underlying pydantic-ai Agent is constructed with TaskDeps as the
    deps_type, mirroring the real temporal tutorial agent. TestModel makes
    the run deterministic and offline.
    """
    model = TestModel(
        call_tools=["get_weather"],
        custom_output_text="The weather in Paris is sunny and 72F.",
    )
    base: Agent[TaskDeps, str] = Agent(model, deps_type=TaskDeps)

    @base.tool_plain
    def get_weather(city: str) -> str:
        """Get the current weather for a city."""
        return f"The weather in {city} is sunny and 72F"

    return TemporalAgent(base, name="test_temporal_agent")


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
# Helpers: the event_stream_handler pattern tested offline
# ---------------------------------------------------------------------------


async def _run_event_stream_handler(
    temporal_agent: TemporalAgent[TaskDeps, str],
    user_msg: str = "What is the weather in Paris?",
    task_id: str = "task1",
) -> _FakeStreaming:
    """Simulate the event_stream_handler activity offline.

    In production the event_stream_handler receives the event stream from
    pydantic-ai's model activity and calls stream_pydantic_ai_events.
    Here we obtain the stream directly from run_stream_events (which works
    offline with TestModel) and forward it to stream_pydantic_ai_events backed
    by a fake streaming backend.

    This is equivalent to:
        async def event_handler(ctx: RunContext[TaskDeps], events: AsyncIterable[AgentStreamEvent]) -> None:
            await stream_pydantic_ai_events(events, ctx.deps.task_id)
    but without requiring a running Temporal server.
    """
    fake_streaming = _FakeStreaming()

    async with temporal_agent.run_stream_events(user_msg) as stream:
        await _fake_stream_pydantic_ai_events(stream, task_id, fake_streaming)

    return fake_streaming


async def _fake_stream_pydantic_ai_events(
    stream: Any,
    task_id: str,
    fake_streaming: _FakeStreaming,
) -> str:
    """Like stream_pydantic_ai_events but uses an injected fake streaming backend.

    Mirrors the exact chain that stream_pydantic_ai_events uses internally:
      PydanticAITurn(stream, coalesce_tool_requests=True)
      + UnifiedEmitter.auto_send_turn(turn)
    but with the fake backend injected so no Redis is needed.
    """
    turn = PydanticAITurn(stream, model=None, coalesce_tool_requests=True)
    emitter = UnifiedEmitter(
        task_id=task_id,
        trace_id=None,
        parent_span_id=None,
        tracer=False,
        streaming=fake_streaming,
    )
    result = await emitter.auto_send_turn(turn)
    return result.final_text


# ---------------------------------------------------------------------------
# Tests: TemporalAgent + event_stream_handler pattern
# ---------------------------------------------------------------------------


class TestTemporalEventStreamHandlerMessageOrder:
    """The event_stream_handler pushes messages in canonical order."""

    async def test_tool_request_before_tool_response(self) -> None:
        """tool_request is pushed before tool_response."""
        temporal_agent = _make_temporal_agent()
        fake_streaming = await _run_event_stream_handler(temporal_agent)

        types = [getattr(m, "type", None) for m in fake_streaming.messages_opened]
        assert "tool_request" in types
        assert "tool_response" in types
        assert types.index("tool_request") < types.index("tool_response")

    async def test_text_is_last(self) -> None:
        """Text content is pushed last (after the tool round-trip)."""
        temporal_agent = _make_temporal_agent()
        fake_streaming = await _run_event_stream_handler(temporal_agent)

        types = [getattr(m, "type", None) for m in fake_streaming.messages_opened]
        assert types[-1] == "text"

    async def test_exactly_three_messages(self) -> None:
        """Exactly tool_request + tool_response + text are pushed."""
        temporal_agent = _make_temporal_agent()
        fake_streaming = await _run_event_stream_handler(temporal_agent)

        assert len(fake_streaming.messages_opened) == 3, (
            f"Expected 3 messages, got {len(fake_streaming.messages_opened)}: "
            f"{[getattr(m, 'type', None) for m in fake_streaming.messages_opened]}"
        )


class TestTemporalEventStreamHandlerContent:
    """Content verification for the messages pushed by the event_stream_handler."""

    async def test_tool_request_is_get_weather(self) -> None:
        """The pushed tool_request is for the get_weather function."""
        temporal_agent = _make_temporal_agent()
        fake_streaming = await _run_event_stream_handler(temporal_agent)

        tool_reqs = [m for m in fake_streaming.messages_opened if isinstance(m, ToolRequestContent)]
        assert len(tool_reqs) == 1
        assert tool_reqs[0].name == "get_weather"

    async def test_tool_response_contains_weather_result(self) -> None:
        """The pushed tool_response contains the get_weather return value."""
        temporal_agent = _make_temporal_agent()
        fake_streaming = await _run_event_stream_handler(temporal_agent)

        tool_resps = [m for m in fake_streaming.messages_opened if isinstance(m, ToolResponseContent)]
        assert len(tool_resps) == 1
        assert "72F" in tool_resps[0].content
        assert tool_resps[0].name == "get_weather"

    async def test_tool_call_ids_match(self) -> None:
        """tool_request and tool_response share the same tool_call_id."""
        temporal_agent = _make_temporal_agent()
        fake_streaming = await _run_event_stream_handler(temporal_agent)

        tool_req = next(m for m in fake_streaming.messages_opened if isinstance(m, ToolRequestContent))
        tool_resp = next(m for m in fake_streaming.messages_opened if isinstance(m, ToolResponseContent))
        assert tool_req.tool_call_id == tool_resp.tool_call_id


class TestTemporalFinalText:
    """stream_pydantic_ai_events returns the correct final text."""

    async def test_final_text_matches_model_output(self) -> None:
        """The returned final text equals the TestModel custom_output_text."""
        temporal_agent = _make_temporal_agent()
        fake_streaming = _FakeStreaming()

        async with temporal_agent.run_stream_events("What is the weather in Paris?") as stream:
            final = await _fake_stream_pydantic_ai_events(stream, "task1", fake_streaming)

        assert final == "The weather in Paris is sunny and 72F."

    async def test_context_lifecycle_complete(self) -> None:
        """Every opened streaming context is also closed."""
        temporal_agent = _make_temporal_agent()
        fake_streaming = await _run_event_stream_handler(temporal_agent)

        opens = [e for e in fake_streaming.sink if e[0] == "open"]
        closes = [e for e in fake_streaming.sink if e[0] == "close"]
        assert len(opens) == len(closes), "Every opened context must be closed"


class TestTemporalAgentStreamEventsOffline:
    """TemporalAgent.run_stream_events produces the expected raw pydantic-ai events.

    This verifies that the TemporalAgent wrapper does not suppress event stream
    delivery when used with TestModel, so the event_stream_handler pattern is
    meaningful offline.
    """

    async def test_run_stream_events_yields_tool_call_and_text(self) -> None:
        """TemporalAgent.run_stream_events with TestModel yields tool + text events."""

        temporal_agent = _make_temporal_agent()
        collected: list[Any] = []

        async with temporal_agent.run_stream_events("What is the weather in Paris?") as stream:
            async for ev in stream:
                collected.append(ev)

        event_types = {type(ev).__name__ for ev in collected}
        assert "FunctionToolResultEvent" in event_types, "Expected FunctionToolResultEvent proving tool call ran"
        assert "PartDeltaEvent" in event_types or "PartEndEvent" in event_types, (
            "Expected text part events in the stream"
        )

    async def test_run_stream_events_contains_tool_result(self) -> None:
        """The raw event stream contains a FunctionToolResultEvent with the tool output."""
        from pydantic_ai.messages import FunctionToolResultEvent

        temporal_agent = _make_temporal_agent()

        async with temporal_agent.run_stream_events("What is the weather in Paris?") as stream:
            events = [ev async for ev in stream]

        tool_results = [ev for ev in events if isinstance(ev, FunctionToolResultEvent)]
        assert len(tool_results) >= 1
        assert "72F" in tool_results[0].part.content


class TestTemporalLiveInfraNote:
    """Placeholder tests documenting what requires live Temporal infrastructure.

    These tests are skipped by design. They document the gap between what the
    offline tests cover and what a full integration test would exercise.
    """

    @pytest.mark.skip(
        reason=(
            "Requires live Temporal server + Redis + ACP server + worker. "
            "See examples/tutorials/10_async/10_temporal/110_pydantic_ai/tests/test_agent.py "
            "for the live integration test that exercises this path end-to-end."
        )
    )
    async def test_temporal_workflow_full_round_trip(self) -> None:
        """Full Temporal workflow: create_task -> send_event -> poll_messages."""
        pass  # Covered by the live tutorial test


@pytest.mark.parametrize(
    "user_msg",
    [
        "What is the weather in Paris?",
        "Tell me the weather in London.",
    ],
)
async def test_temporal_handler_pushes_messages_for_various_inputs(user_msg: str) -> None:
    """event_stream_handler pushes tool_request + tool_response + text for any input."""
    temporal_agent = _make_temporal_agent()
    fake_streaming = await _run_event_stream_handler(temporal_agent, user_msg=user_msg)

    types = [getattr(m, "type", None) for m in fake_streaming.messages_opened]
    assert "tool_request" in types
    assert "tool_response" in types
    assert "text" in types
