from __future__ import annotations

from typing import Any, Literal, cast

from agentex.types.span import Span

# Reserved key under ``Span.data`` carrying failure info for a span whose
# context-manager body raised. Mirrors the existing ``__span_type__`` /
# ``__source__`` reserved-key convention already read/written by the SGP
# processor. Stored in ``data`` because the Span model is generated from the
# OpenAPI spec and has no first-class status/error field; ``data`` is a real
# field, so it survives ``model_copy(deep=True)`` and round-trips to both the
# SGP and agentex-native span stores.
SPAN_ERROR_KEY = "__error__"

ErrorCategory = Literal["application", "platform", "unknown"]
ERROR_CATEGORY_UNKNOWN: ErrorCategory = "unknown"
_ERROR_CATEGORIES = frozenset({"application", "platform", "unknown"})


class CategorizedError(Exception):
    """Base class for failures with known operational ownership.

    Use ``ApplicationError`` for failures owned by agent or caller code, such
    as business logic, user input, tools, or application configuration. Use
    ``PlatformError`` only at a known Agentex/SGP-owned boundary, such as
    managed runtime, tracing, persistence, or platform networking. Leave
    unclassified failures as ordinary exceptions so they remain ``unknown``.
    """

    error_category: ErrorCategory = ERROR_CATEGORY_UNKNOWN


class ApplicationError(CategorizedError):
    """Failure owned by the agent application or its caller."""

    error_category: ErrorCategory = "application"


class PlatformError(CategorizedError):
    """Failure owned by Agentex/SGP or a platform-managed dependency."""

    error_category: ErrorCategory = "platform"


def _normalize_error_category(value: object) -> ErrorCategory | None:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _ERROR_CATEGORIES:
            return cast(ErrorCategory, normalized)
    return None


def _error_category(
    exc: BaseException,
    explicit_category: ErrorCategory | str | None = None,
) -> ErrorCategory:
    """Return an explicit producer classification, defaulting safely to unknown."""
    return (
        _normalize_error_category(explicit_category)
        or (exc.error_category if isinstance(exc, CategorizedError) else None)
        or ERROR_CATEGORY_UNKNOWN
    )


def set_span_error(
    span: Span,
    exc: BaseException,
    *,
    error_category: ErrorCategory | str | None = None,
) -> None:
    """Record an exception on ``span`` under ``data[SPAN_ERROR_KEY]``.

    An explicit ``error_category`` takes precedence over a ``CategorizedError``
    classification. Invalid or absent categories become unknown.
    No-op when ``span.data`` is a list (matching ``_add_source_to_span``, which
    only attaches metadata to dict-shaped data).
    """
    error = {
        "type": type(exc).__name__,
        "message": str(exc),
        "category": _error_category(exc, error_category),
    }
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
