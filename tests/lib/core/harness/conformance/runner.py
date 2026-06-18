"""Shared conformance engine: every harness tap registers fixtures here.

A fixture is (name, list[StreamTaskMessage]). The runner asserts that span
derivation over the events is identical regardless of delivery channel, which is
the cross-channel guarantee from the spec.

Registry shared-state hazard: `_REGISTRY` is process-global. Every `test_*.py`
module that calls `register()` at import time contributes to it, so a module
that parametrizes over `all_fixtures()` will see fixtures registered by ANY
other conformance module imported earlier in the same pytest process (collection
order is not guaranteed). To stay deterministic, each future harness conformance
module should register and parametrize over its OWN fixtures (e.g. keep a
module-local list it both registers and parametrizes), rather than relying on
cross-module global accumulation via `all_fixtures()`.
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
