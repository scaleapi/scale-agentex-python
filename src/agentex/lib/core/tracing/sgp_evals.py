"""Run/row attribution for spans of SGP evals generation-unit tasks.

The evals service tags each unit's task with ``task_metadata`` carrying
``sgp_evals`` plus the run, row and attempt it belongs to. The ids are copied
onto the SGP copy of every span as flat ``sgp_evals_*`` keys so a spans search
on ``extra_metadata`` finds a unit's spans. Flat because sgp-traces treats
dotted keys differently on ClickHouse and Postgres.
"""

from __future__ import annotations

import threading
from typing import Any
from datetime import UTC, datetime
from collections import OrderedDict

from agentex.types.span import Span

__all__ = (
    "MEMO_KEY",
    "register_task",
    "register_workflow_task",
    "register_task_metadata",
    "span_attrs_from_task_metadata",
    "attrs_for_span",
    "enable_capture",
    "capture_for_span",
    "release_span",
)

TASK_METADATA_MARKER = "sgp_evals"
SPAN_KEY_PREFIX = "sgp_evals_"
_TASK_METADATA_KEYS = ("generation_run_id", "row_id", "attempt_idx")
# Temporal workflow memo key the ACP server sets so the worker process can stamp the same attrs.
MEMO_KEY = "sgp_evals_span_attrs"

# Only eval tasks are stored, so this stays tiny. The LRU bound caps a long-lived agent process.
_MAX_TASKS = 10_000
# Each task's attrs with when they took effect, so an unpinned span only gets attrs its task had at its start.
_attrs_by_task: OrderedDict[str, tuple[dict[str, Any], datetime]] = OrderedDict()
# Attrs captured when a span starts, so a later registry change cannot alter a span still queued for export.
_attrs_by_span: OrderedDict[str, dict[str, Any]] = OrderedDict()
# Spans pinned with no attrs live apart so a flood of plain spans cannot evict an eval span's pinned ids.
_plain_spans: OrderedDict[str, None] = OrderedDict()
_lock = threading.Lock()
_WHOLE_WORKFLOW = datetime.min.replace(tzinfo=UTC)
# Only the SGP processor reads the pins, so a process without one never takes the lock per span.
_capture_enabled = False


def span_attrs_from_task_metadata(task_metadata: Any) -> dict[str, Any] | None:
    """The flat span attrs for an evals generation-unit task, or None for any other task."""
    if not isinstance(task_metadata, dict) or task_metadata.get(TASK_METADATA_MARKER) is None:
        return None
    attrs = {
        f"{SPAN_KEY_PREFIX}{key}": task_metadata[key] for key in _TASK_METADATA_KEYS if task_metadata.get(key) is not None
    }
    return attrs or None


def register_task(task_id: str, attrs: dict[str, Any], effective_from: datetime | None = None) -> None:
    with _lock:
        since = effective_from or datetime.now(UTC)
        current = _attrs_by_task.get(task_id)
        # Every event re-registers the same attrs, which must not move their start past the task's earlier spans.
        if current is not None and current[0] == attrs:
            since = min(since, current[1])
        _attrs_by_task[task_id] = (attrs, since)
        _attrs_by_task.move_to_end(task_id)
        while len(_attrs_by_task) > _MAX_TASKS:
            _attrs_by_task.popitem(last=False)


def register_workflow_task(task_id: str, attrs: dict[str, Any]) -> None:
    """Register ids read from a workflow memo, which also cover spans the workflow started before this worker saw it."""
    register_task(task_id, attrs, effective_from=_WHOLE_WORKFLOW)


def register_task_metadata(task_id: str, task_metadata: Any) -> dict[str, Any] | None:
    """Remember an eval task's span attrs. No-op (and no lookup cost) for every other task."""
    attrs = span_attrs_from_task_metadata(task_metadata)
    if attrs is not None:
        register_task(task_id, attrs)
    else:
        unregister_task(task_id)
    return attrs


def unregister_task(task_id: str) -> None:
    if _attrs_by_task:
        with _lock:
            _attrs_by_task.pop(task_id, None)


def _lookup(span: Span, started_at: datetime | None = None) -> dict[str, Any]:
    for key in (span.task_id, span.trace_id):
        entry = _attrs_by_task.get(key) if key else None
        if entry is not None and (started_at is None or entry[1] <= started_at):
            return dict(entry[0])
    return {}


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def enable_capture() -> None:
    global _capture_enabled
    _capture_enabled = True


def capture_for_span(span: Span) -> None:
    """Pin the span's attrs at start, empty included, so an eval task registered later cannot claim it."""
    if not _capture_enabled:
        return
    with _lock:
        attrs = _lookup(span)
        store: OrderedDict[str, Any] = _attrs_by_span if attrs else _plain_spans
        store[span.id] = attrs or None
        while len(store) > _MAX_TASKS:
            store.popitem(last=False)


def release_span(span_id: str) -> None:
    if _attrs_by_span or _plain_spans:
        with _lock:
            _attrs_by_span.pop(span_id, None)
            _plain_spans.pop(span_id, None)


def attrs_for_span(span: Span) -> dict[str, Any]:
    """Attrs captured at span start, else those its task (``span.task_id`` then ``span.trace_id``) had at its start."""
    if not _attrs_by_task and not _attrs_by_span and not _plain_spans:
        return {}
    with _lock:
        if span.id in _attrs_by_span:
            return dict(_attrs_by_span[span.id])
        if span.id in _plain_spans:
            return {}
        # Unpinned (started on another worker, before an SGP processor existed, or evicted).
        return _lookup(span, _aware(span.start_time))


def clear() -> None:
    """Reset the registry (test isolation)."""
    with _lock:
        _attrs_by_task.clear()
        _attrs_by_span.clear()
        _plain_spans.clear()
