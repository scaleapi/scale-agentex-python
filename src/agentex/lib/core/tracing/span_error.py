from __future__ import annotations

from typing import Any

from agentex.types.span import Span

# Reserved key under ``Span.data`` carrying failure info for a span whose
# context-manager body raised. Mirrors the existing ``__span_type__`` /
# ``__source__`` reserved-key convention already read/written by the SGP
# processor. Stored in ``data`` because the Span model is generated from the
# OpenAPI spec and has no first-class status/error field; ``data`` is a real
# field, so it survives ``model_copy(deep=True)`` and round-trips to both the
# SGP and agentex-native span stores.
SPAN_ERROR_KEY = "__error__"


def set_span_error(span: Span, exc: BaseException) -> None:
    """Record an exception on ``span`` under ``data[SPAN_ERROR_KEY]``.

    No-op when ``span.data`` is a list (matching ``_add_source_to_span``, which
    only attaches metadata to dict-shaped data).
    """
    error = {"type": type(exc).__name__, "message": str(exc)}
    if span.data is None:
        span.data = {}
    if isinstance(span.data, dict):
        span.data[SPAN_ERROR_KEY] = error


def get_span_error(span: Span) -> dict[str, Any] | None:
    """Return the error recorded by :func:`set_span_error`, or ``None``."""
    if isinstance(span.data, dict):
        value = span.data.get(SPAN_ERROR_KEY)
        if isinstance(value, dict):
            return value
    return None
