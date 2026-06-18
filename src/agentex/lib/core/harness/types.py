"""Types for the unified harness surface."""

from __future__ import annotations

from typing import Any, Union, Literal, Protocol, AsyncIterator, runtime_checkable
from dataclasses import field, dataclass

from pydantic import BaseModel, ConfigDict

from agentex.types.task_message_update import (
    StreamTaskMessageDone,
    StreamTaskMessageFull,
    StreamTaskMessageDelta,
    StreamTaskMessageStart,
)

# The canonical stream element. Taps yield these; delivery adapters consume them.
StreamTaskMessage = Union[
    StreamTaskMessageStart,
    StreamTaskMessageDelta,
    StreamTaskMessageFull,
    StreamTaskMessageDone,
]

SpanKind = Literal["tool", "reasoning", "subagent"]


@dataclass
class OpenSpan:
    """Signal to open a child span. `key` pairs an open with its close."""

    key: str
    kind: SpanKind
    name: str
    input: dict[str, Any] = field(default_factory=dict)


@dataclass
class CloseSpan:
    """Signal to close the span previously opened with the same `key`."""

    key: str
    output: Any = None
    is_complete: bool = True  # False when closed by flush() without a result


SpanSignal = Union[OpenSpan, CloseSpan]


class TurnUsage(BaseModel):
    """Harness-independent turn usage/cost, attached to the turn span.

    Token field names align with agentex.lib.core.observability.llm_metrics.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    duration_ms: int | None = None
    num_llm_calls: int = 0
    num_tool_calls: int = 0
    num_reasoning_blocks: int = 0


class TurnResult(BaseModel):
    """Returned to the caller after a turn is delivered."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    final_text: str = ""
    usage: TurnUsage = TurnUsage()


@runtime_checkable
class HarnessTurn(Protocol):
    """A single harness turn: a canonical stream plus its normalized usage.

    Python async generators cannot cleanly return a value to their consumer, so
    a tap exposes usage via `usage()` (valid only after `events` is exhausted)
    rather than via StopAsyncIteration.
    """

    @property
    def events(self) -> AsyncIterator[StreamTaskMessage]: ...

    def usage(self) -> TurnUsage: ...
