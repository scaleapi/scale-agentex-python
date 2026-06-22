"""Tracing handler that records Agentex spans for tool calls in a pydantic-ai agent run.

.. deprecated::
    ``AgentexPydanticAITracingHandler`` and ``create_pydantic_ai_tracing_handler``
    are superseded by the unified harness surface (``UnifiedEmitter`` in
    ``agentex.lib.core.harness``). The unified surface derives tool and
    reasoning spans directly from the canonical ``StreamTaskMessage*`` stream,
    so no separate handler is required. Both symbols remain fully importable
    and functional; they will be removed in a future release. New code should
    construct a ``UnifiedEmitter`` with a ``trace_id`` instead:

        from agentex.lib.core.harness import UnifiedEmitter
        from agentex.lib.adk._modules._pydantic_ai_turn import PydanticAITurn

        emitter = UnifiedEmitter(task_id=task_id, trace_id=trace_id, parent_span_id=parent_span_id)
        turn = PydanticAITurn(agent.run_stream_events(prompt), model="openai:gpt-4o")
        async for event in emitter.yield_turn(turn):
            yield event

# NOTE: A runtime ``warnings.warn(..., DeprecationWarning)`` is intentionally
# omitted here. The repo's pyproject ``filterwarnings = ["error"]`` would turn
# it into a test/caller failure, and the async helper (``stream_pydantic_ai_events``)
# still threads this handler through for existing callers that lack a ``trace_id``
# on the async path. The runtime warning and caller migration are deferred until
# ``trace_id`` threading lands on the async helper in a future API-versioning change.

Mirrors the LangGraph tracing handler pattern: the caller creates a handler
bound to a ``trace_id`` and a ``parent_span_id``, then hands it to
``stream_pydantic_ai_events(..., tracing_handler=handler)``. The streamer
calls ``on_tool_start`` / ``on_tool_end`` as it observes the corresponding
events in the agent stream, and the handler records one Agentex child span
per tool call.

Why a handler-on-the-streamer rather than an OpenTelemetry bridge:
pydantic-ai exposes its stream of ``AgentStreamEvent`` directly, and that
stream already contains every signal we need to record tool spans. Going
through an OTel processor would require setting up an OTel ``TracerProvider``
plus a bridge processor — that's a much larger investment, and orthogonal
to the streaming path we already own. This handler hooks into the same
event stream the UI-streaming helper consumes, so a single pass over the
events produces both: live deltas on Redis and child spans on the AgentEx
tracing pipeline.

Why span IDs are derived from ``tool_call_id`` instead of held in a dict:
pydantic-ai's ``TemporalAgent`` splits the agent run across one or more
Temporal activities. The ``event_stream_handler`` is invoked once per
activity, with a fresh handler instance each time. So ``on_tool_start``
(emitted inside the model activity that issued the tool call) and
``on_tool_end`` (emitted inside the next model activity, after the tool
runs) land in different handler instances — an in-memory dict can't pair
them. Deriving the span ID deterministically from ``(trace_id,
tool_call_id)`` makes the open/close pairing stateless: ``on_tool_end``
re-derives the same ID and PATCHes the existing span directly.

Span hierarchy produced::

    <parent span>        (e.g. "Turn N", created by the caller)
      ├── tool:<name>    (one child span per tool call)
      └── tool:<name>
"""

from __future__ import annotations

import uuid
from typing import Any
from datetime import UTC, datetime

from agentex import AsyncAgentex
from agentex.lib.utils.logging import make_logger
from agentex.lib.adk._modules.tracing import TracingModule
from agentex.lib.adk.utils._modules.client import create_async_agentex_client

logger = make_logger(__name__)


# Stable namespace for deriving tool-call span IDs. The exact UUID value is
# arbitrary; it just needs to be a constant so the same (trace_id, tool_call_id)
# always maps to the same span ID across handler invocations.
_TOOL_SPAN_NAMESPACE = uuid.UUID("8c2f9a2b-3e4d-4b5a-9c1f-0a1b2c3d4e5f")


def _tool_span_id(trace_id: str, tool_call_id: str) -> str:
    """Deterministic span ID for a given tool call within a trace."""
    return str(uuid.uuid5(_TOOL_SPAN_NAMESPACE, f"{trace_id}:{tool_call_id}"))


class AgentexPydanticAITracingHandler:
    """Records Agentex tracing spans for tool calls observed in a pydantic-ai event stream.

    .. deprecated::
        Superseded by ``UnifiedEmitter`` (``agentex.lib.core.harness``), which
        derives tool and reasoning spans from the canonical ``StreamTaskMessage*``
        stream automatically when ``trace_id`` is provided. This class remains
        fully functional but will be removed in a future release. New code should
        use ``UnifiedEmitter`` with a trace context instead of constructing this
        handler directly.

    Pass an instance to ``stream_pydantic_ai_events(..., tracing_handler=...)``
    or call ``on_tool_start`` / ``on_tool_end`` yourself if you're consuming
    the event stream by hand.
    """

    def __init__(
        self,
        trace_id: str,
        parent_span_id: str | None = None,
        task_id: str | None = None,
        tracing: TracingModule | None = None,
        client: AsyncAgentex | None = None,
    ) -> None:
        self._trace_id = trace_id
        self._parent_span_id = parent_span_id
        # task_id on the span record (separate from trace_id) is what the
        # AgentEx UI's per-task spans dropdown filters by. If you want your
        # tool spans visible in that dropdown, set this to the task ID.
        self._task_id = task_id
        # ``_tracing`` is retained for callers / tests that want to inject a
        # mocked TracingModule, even though the on_tool_* methods now go
        # direct to the AgentEx client (see module docstring for why).
        self._tracing_eager = tracing
        self._tracing_lazy: TracingModule | None = None
        # Defer client construction until first use so httpx binds to the
        # running event loop (matches the TracingModule pattern).
        self._client_eager = client
        self._client_lazy: AsyncAgentex | None = None

    @property
    def _tracing(self) -> TracingModule:
        if self._tracing_eager is not None:
            return self._tracing_eager
        if self._tracing_lazy is None:
            self._tracing_lazy = TracingModule()
        return self._tracing_lazy

    @property
    def _client(self) -> AsyncAgentex:
        if self._client_eager is not None:
            return self._client_eager
        if self._client_lazy is None:
            self._client_lazy = create_async_agentex_client()
        return self._client_lazy

    async def on_tool_start(
        self,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any] | str | None,
    ) -> None:
        """Open a child span for a tool call.

        Uses a deterministic span ID derived from ``tool_call_id`` so that
        ``on_tool_end`` — which may run inside a different handler instance
        when pydantic-ai splits the run across Temporal activities — can
        close the same span without needing in-memory state.
        """
        span_id = _tool_span_id(self._trace_id, tool_call_id)
        await self._client.spans.create(
            id=span_id,
            trace_id=self._trace_id,
            task_id=self._task_id,
            parent_id=self._parent_span_id,
            name=f"tool:{tool_name}" if tool_name else "tool",
            start_time=datetime.now(UTC),
            input={"arguments": arguments},
            data={"__span_type__": "CUSTOM"},
        )

    async def on_tool_end(self, tool_call_id: str, result: Any) -> None:
        """Close a child span by PATCHing its end_time and output.

        Re-derives the deterministic span ID from ``tool_call_id`` and updates
        the existing span record directly. No in-memory span lookup, so this
        works even when ``on_tool_start`` ran inside a different handler
        instance (e.g. across pydantic-ai TemporalAgent activity boundaries).
        """
        span_id = _tool_span_id(self._trace_id, tool_call_id)
        await self._client.spans.update(
            span_id,
            end_time=datetime.now(UTC),
            output={"result": result},
        )

    async def on_tool_error(self, tool_call_id: str, error: BaseException | str) -> None:
        """Close a child span with an error payload as output."""
        span_id = _tool_span_id(self._trace_id, tool_call_id)
        await self._client.spans.update(
            span_id,
            end_time=datetime.now(UTC),
            output={"error": str(error)},
        )


def create_pydantic_ai_tracing_handler(
    trace_id: str,
    parent_span_id: str | None = None,
    task_id: str | None = None,
) -> AgentexPydanticAITracingHandler:
    """Create a tracing handler that records Agentex spans for pydantic-ai tool calls.

    .. deprecated::
        Superseded by ``UnifiedEmitter`` (``agentex.lib.core.harness``), which
        derives tool and reasoning spans from the canonical ``StreamTaskMessage*``
        stream automatically when ``trace_id`` is provided. This function remains
        fully functional but will be removed in a future release. New code should
        construct a ``UnifiedEmitter`` with a trace context instead.

    Args:
        trace_id: The trace ID. Typically the Agentex task ID.
        parent_span_id: Optional parent span ID to nest tool spans under. If
            omitted, the tool spans become trace-root spans.
        task_id: Optional task ID stamped onto each span. Required for the
            AgentEx UI's per-task spans dropdown to display the spans.

    Returns:
        A handler suitable for passing to ``stream_pydantic_ai_events(..., tracing_handler=...)``.
    """
    return AgentexPydanticAITracingHandler(
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        task_id=task_id,
    )
