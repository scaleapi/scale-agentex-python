"""UnifiedEmitter: the single facade agent authors use for either delivery mode."""

from __future__ import annotations

from typing import AsyncGenerator
from datetime import datetime

from agentex.lib.core.harness.types import TurnResult, HarnessTurn, StreamTaskMessage
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.auto_send import auto_send
from agentex.lib.core.harness.yield_delivery import yield_events


class UnifiedEmitter:
    """Ties trace context + chosen delivery together.

    Tracing modes (the `tracer` arg):
    - tracer=None (default): auto-construct a SpanTracer if `trace_id` is present.
    - tracer=False: disable tracing entirely, regardless of `trace_id`.
    - tracer=<SpanTracer>: use the supplied instance.

    `tracing` and `streaming` are injection escape-hatches for tests/advanced
    use; leave them None in production so the real adk modules are used.
    """

    tracer: SpanTracer | None

    def __init__(
        self,
        task_id: str,
        trace_id: str | None,
        parent_span_id: str | None,
        tracer: SpanTracer | bool | None = None,
        tracing: object | None = None,
        streaming: object | None = None,
    ):
        self.task_id = task_id
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        self._streaming = streaming
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

    async def yield_turn(self, turn: HarnessTurn) -> AsyncGenerator[StreamTaskMessage, None]:
        """Sync HTTP ACP delivery: forward events, trace as side effect."""
        async for event in yield_events(turn.events, tracer=self.tracer):
            yield event

    async def auto_send_turn(self, turn: HarnessTurn, created_at: datetime | None = None) -> TurnResult:
        """Async/temporal delivery: push to the task stream, return TurnResult.

        Pass `created_at` (e.g. `workflow.now()` under Temporal) to stamp the
        turn's messages with a deterministic timestamp; it is forwarded to the
        streaming contexts. Default None preserves server-side timestamps.
        """
        # `turn.usage()` is only valid AFTER `turn.events` is exhausted (the
        # HarnessTurn single-pass contract: real turns populate usage while the
        # stream is consumed). So drive delivery first, then read usage — do NOT
        # pass `usage=turn.usage()` eagerly here (that would capture the empty
        # default before the stream runs).
        result = await auto_send(
            turn.events,
            task_id=self.task_id,
            tracer=self.tracer,
            streaming=self._streaming,
            created_at=created_at,
        )
        result.usage = turn.usage()
        return result
