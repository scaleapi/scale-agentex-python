"""Shared test doubles for the unified harness test suites.

A single superset implementation of the in-memory tracing backend used across
the harness tests. Three recording shapes were previously duplicated:

- Shape-1 (richest): ``started`` = ``(name, parent_id, input)`` 3-tuples,
  ``ended`` = ``(name, output)`` 2-tuples, plus an ``ended_spans`` list of the
  closed ``FakeSpan`` objects (which carry ``.name``, ``.output``, ``.data``).
- Shape-2: ``started`` = ``(name, parent_id)`` 2-tuples, ``ended`` =
  ``(name, output)``.
- Shape-3: ``started`` = bare names, ``ended`` = bare outputs.

``FakeTracing`` records the richest (shape-1) form and exposes read-only
convenience properties (``started_names``, ``started_pairs``,
``ended_outputs``) so shape-2 and shape-3 assertions stay clean.
"""

from __future__ import annotations

from typing import Any


class FakeSpan:
    def __init__(self, name: str) -> None:
        self.name = name
        self.output: Any = None
        self.data: Any = None


class FakeTracing:
    def __init__(self) -> None:
        self.started: list[tuple[str, Any, Any]] = []
        self.ended: list[tuple[str, Any]] = []
        self.ended_spans: list[FakeSpan] = []

    async def start_span(
        self,
        *,
        trace_id: str,
        name: str,
        input: Any = None,
        parent_id: Any = None,
        data: Any = None,
        task_id: Any = None,
    ) -> FakeSpan:
        self.started.append((name, parent_id, input))
        return FakeSpan(name)

    async def end_span(self, *, trace_id: str, span: FakeSpan) -> None:
        self.ended.append((span.name, span.output))
        self.ended_spans.append(span)

    @property
    def started_names(self) -> list[str]:
        return [name for (name, _parent, _input) in self.started]

    @property
    def started_pairs(self) -> list[tuple[str, Any]]:
        return [(name, parent) for (name, parent, _input) in self.started]

    @property
    def ended_outputs(self) -> list[Any]:
        return [output for (_name, output) in self.ended]
