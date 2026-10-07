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
from collections import OrderedDict

from agentex.types.span import Span

__all__ = ("MEMO_KEY", "register_task", "register_task_metadata", "span_attrs_from_task_metadata", "attrs_for_span")

TASK_METADATA_MARKER = "sgp_evals"
SPAN_KEY_PREFIX = "sgp_evals_"
_TASK_METADATA_KEYS = ("generation_run_id", "row_id", "attempt_idx")
# Temporal workflow memo key the ACP server sets so the worker process can stamp the same attrs.
MEMO_KEY = "sgp_evals_span_attrs"

# Only eval tasks are stored, so this stays tiny. The LRU bound caps a long-lived agent process.
_MAX_TASKS = 10_000
_attrs_by_task: OrderedDict[str, dict[str, Any]] = OrderedDict()
_lock = threading.Lock()


def span_attrs_from_task_metadata(task_metadata: Any) -> dict[str, Any] | None:
    """The flat span attrs for an evals generation-unit task, or None for any other task."""
    if not isinstance(task_metadata, dict) or task_metadata.get(TASK_METADATA_MARKER) is None:
        return None
    attrs = {
        f"{SPAN_KEY_PREFIX}{key}": task_metadata[key] for key in _TASK_METADATA_KEYS if task_metadata.get(key) is not None
    }
    return attrs or None


def register_task(task_id: str, attrs: dict[str, Any]) -> None:
    with _lock:
        _attrs_by_task[task_id] = attrs
        _attrs_by_task.move_to_end(task_id)
        while len(_attrs_by_task) > _MAX_TASKS:
            _attrs_by_task.popitem(last=False)


def register_task_metadata(task_id: str, task_metadata: Any) -> dict[str, Any] | None:
    """Remember an eval task's span attrs. No-op (and no lookup cost) for every other task."""
    attrs = span_attrs_from_task_metadata(task_metadata)
    if attrs is not None:
        register_task(task_id, attrs)
    return attrs


def attrs_for_span(span: Span) -> dict[str, Any]:
    """Attrs for the task a span belongs to, found by ``span.task_id`` then ``span.trace_id``."""
    if not _attrs_by_task:
        return {}
    with _lock:
        for key in (span.task_id, span.trace_id):
            if key and key in _attrs_by_task:
                return dict(_attrs_by_task[key])
    return {}


def clear() -> None:
    """Reset the registry (test isolation)."""
    with _lock:
        _attrs_by_task.clear()
