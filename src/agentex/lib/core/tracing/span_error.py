from __future__ import annotations

import os
from typing import Any, cast

from scale_gp_beta.lib.tracing import (
    ERROR_CLASSIFIER_VERSION as ERROR_CLASSIFIER_VERSION,
    PlatformError as PlatformError,
    ApplicationError as ApplicationError,
    CategorizedError as CategorizedError,
    ExceptionMapping as ExceptionMapping,
    ErrorClassification as ErrorClassification,
    ErrorClassifierConfig as ErrorClassifierConfig,
    TracebackOwnershipPolicy,
    classify_error,
)
from scale_gp_beta.lib.tracing.types import ErrorCategory

from agentex.types.span import Span

# Reserved key under ``Span.data`` carrying failure info for a span whose
# context-manager body raised. Mirrors the existing ``__span_type__`` /
# ``__source__`` reserved-key convention already read/written by the SGP
# processor. Stored in ``data`` because the Span model is generated from the
# OpenAPI spec and has no first-class status/error field; ``data`` is a real
# field, so it survives ``model_copy(deep=True)`` and round-trips to both the
# SGP and agentex-native span stores.
SPAN_ERROR_KEY = "__error__"

_AGENTEX_PACKAGE_ROOT = os.path.normcase(os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
AGENTEX_ERROR_CLASSIFIER_CONFIG = ErrorClassifierConfig(
    policy=TracebackOwnershipPolicy(
        platform_module_prefixes=("agentex",),
        platform_file_roots=(_AGENTEX_PACKAGE_ROOT,),
        infer_application_from_unowned_absolute_paths=True,
    )
)


def set_span_error(
    span: Span,
    exc: BaseException,
    *,
    error_category: ErrorCategory | str | None = None,
    boundary_category: ErrorCategory | None = None,
    mapping_scope: str | None = None,
    classifier_config: ErrorClassifierConfig = AGENTEX_ERROR_CLASSIFIER_CONFIG,
) -> None:
    """Record an exception on ``span`` under ``data[SPAN_ERROR_KEY]``.

    The shared Scale GP classifier inspects the exception's existing traceback
    using Agentex's ownership policy. Explicit and typed categories remain
    authoritative; boundary hints and scoped mappings are fallback signals.
    No-op when ``span.data`` is a list (matching ``_add_source_to_span``, which
    only attaches metadata to dict-shaped data).
    """
    classification = classify_error(
        exc,
        explicit_category=cast(ErrorCategory | None, error_category),
        boundary_category=boundary_category,
        mapping_scope=mapping_scope,
        config=classifier_config,
    )
    error = {
        "type": type(exc).__name__,
        "message": str(exc),
        "category": classification.category,
        "category_source": classification.source,
        "classifier_version": classification.classifier_version,
        "category_reason": classification.reason,
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
