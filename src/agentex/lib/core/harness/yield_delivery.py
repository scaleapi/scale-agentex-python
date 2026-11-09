"""Yield delivery: pass the canonical stream through, tracing as a side effect."""

from __future__ import annotations

import contextlib
from typing import AsyncIterator, AsyncGenerator

from agentex.lib.core.harness.types import StreamTaskMessage
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.span_derivation import SpanDeriver


async def yield_events(
    events: AsyncIterator[StreamTaskMessage],
    tracer: SpanTracer | None = None,
) -> AsyncGenerator[StreamTaskMessage, None]:
    """Forward each event to the caller; derive + trace spans as a side effect.

    For sync HTTP ACP agents that yield events back over the response. When
    `tracer` is None, this is a pure passthrough.

    The finally also closes `events` (when it exposes `aclose`), so a consumer
    that stops early — a client disconnect closes this generator — tears the tap
    down instead of leaving it suspended at a yield: the turn object pins its
    event generator, so GC does not rescue it and the harness subprocess leaks.
    Closing an exhausted generator is a no-op, and a failure there is suppressed
    so it cannot mask the original exception.
    """
    deriver = SpanDeriver() if tracer is not None else None
    try:
        async for event in events:
            if deriver is not None and tracer is not None:
                for signal in deriver.observe(event):
                    await tracer.handle(signal)
            yield event
    finally:
        try:
            if deriver is not None and tracer is not None:
                for signal in deriver.flush():
                    await tracer.handle(signal)
        finally:
            aclose = getattr(events, "aclose", None)
            if aclose is not None:
                with contextlib.suppress(Exception):
                    await aclose()
