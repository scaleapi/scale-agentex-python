"""UnifiedEmitter: the single facade agent authors use for either delivery mode."""

from __future__ import annotations

from typing import AsyncIterator

from agentex.lib.core.harness.auto_send import auto_send
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.types import HarnessTurn, StreamTaskMessage, TurnResult
from agentex.lib.core.harness.yield_delivery import yield_events


class UnifiedEmitter:
    """Ties trace context + chosen delivery together.

    Tracing is default-on whenever `trace_id` is truthy; pass `tracer=False` to
    disable, or a custom `SpanTracer` to override.
    """

    tracer: SpanTracer | None

    def __init__(
        self,
        task_id: str,
        trace_id: str | None,
        parent_span_id: str | None,
        tracer: SpanTracer | bool | None = None,
        tracing: object | None = None,
    ):
        self.task_id = task_id
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        if tracer is False:
            self.tracer = None
        elif isinstance(tracer, SpanTracer):
            self.tracer = tracer
        elif trace_id:
            self.tracer = SpanTracer(
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                task_id=task_id,
                tracing=tracing,
            )
        else:
            self.tracer = None

    async def yield_turn(self, turn: HarnessTurn) -> AsyncIterator[StreamTaskMessage]:
        """Sync HTTP ACP delivery: forward events, trace as side effect."""
        async for event in yield_events(turn.events, tracer=self.tracer):
            yield event

    async def auto_send_turn(self, turn: HarnessTurn) -> TurnResult:
        """Async/temporal delivery: push to the task stream, return TurnResult."""
        return await auto_send(
            turn.events,
            task_id=self.task_id,
            tracer=self.tracer,
            usage=turn.usage(),
        )
