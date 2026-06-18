"""Shared, harness-independent machinery for the unified harness surface.

The Agentex StreamTaskMessage* stream is the single source of truth; this
package derives spans from it and delivers it (yield or auto-send), so every
harness tap gets streaming + tracing + turn usage uniformly.
"""

from agentex.lib.core.harness.emitter import UnifiedEmitter
from agentex.lib.core.harness.tracer import SpanTracer
from agentex.lib.core.harness.types import (
    CloseSpan,
    HarnessTurn,
    OpenSpan,
    SpanSignal,
    StreamTaskMessage,
    TurnResult,
    TurnUsage,
)

__all__ = [
    "UnifiedEmitter",
    "SpanTracer",
    "OpenSpan",
    "CloseSpan",
    "SpanSignal",
    "StreamTaskMessage",
    "TurnUsage",
    "TurnResult",
    "HarnessTurn",
]
