"""Yield delivery: pass the canonical stream through, tracing as a side effect."""

from __future__ import annotations

from typing import AsyncGenerator, AsyncIterator

from agentex.lib.core.harness.span_derivation import SpanDeriver
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.types import StreamTaskMessage


async def yield_events(
    events: AsyncIterator[StreamTaskMessage],
    tracer: SpanTracer | None = None,
) -> AsyncGenerator[StreamTaskMessage, None]:
    """Forward each event to the caller; derive + trace spans as a side effect.

    For sync HTTP ACP agents that yield events back over the response. When
    `tracer` is None, this is a pure passthrough.
    """
    deriver = SpanDeriver() if tracer is not None else None
    try:
        async for event in events:
            if deriver is not None:  # tracer is non-None whenever deriver is set
                for signal in deriver.observe(event):
                    await tracer.handle(signal)
            yield event
    finally:
        if deriver is not None:  # tracer is non-None whenever deriver is set
            for signal in deriver.flush():
                await tracer.handle(signal)
