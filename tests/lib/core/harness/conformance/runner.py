"""Shared conformance engine: every harness tap registers fixtures here.

A fixture is (name, list[StreamTaskMessage]). The runner asserts that span
derivation over the events is identical regardless of delivery channel, which is
the cross-channel guarantee from the spec.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentex.lib.core.harness.span_derivation import SpanDeriver
from agentex.lib.core.harness.types import SpanSignal, StreamTaskMessage


@dataclass
class Fixture:
    name: str
    events: list[StreamTaskMessage]


_REGISTRY: list[Fixture] = []


def register(fixture: Fixture) -> None:
    _REGISTRY.append(fixture)


def all_fixtures() -> list[Fixture]:
    return list(_REGISTRY)


def derive_all(events: list[StreamTaskMessage]) -> list[SpanSignal]:
    d = SpanDeriver()
    out: list[SpanSignal] = []
    for e in events:
        out.extend(d.observe(e))
    out.extend(d.flush())
    return out
