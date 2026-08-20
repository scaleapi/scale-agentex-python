from __future__ import annotations

import os
import sysconfig
from enum import Enum
from types import TracebackType
from typing import Any, Literal, cast
from dataclasses import dataclass
from collections.abc import Sequence

from scale_gp_beta.lib.tracing import (
    PlatformError as PlatformError,
    ApplicationError as ApplicationError,
    CategorizedError,
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

ERROR_CATEGORY_UNKNOWN: ErrorCategory = "unknown"
ERROR_CLASSIFIER_VERSION = "agentex-ownership-v2"
_ERROR_CATEGORIES = frozenset({"application", "platform", "unknown"})

ErrorCategorySource = Literal["explicit", "categorized_error", "stack_trace", "boundary", "mapping", "fallback"]
FrameOwnership = Literal["application", "platform", "ignored", "unresolved", "ambiguous"]


class ErrorBoundary(str, Enum):
    """Agentex boundaries whose ownership is known without inspecting an error."""

    AGENT_EXECUTION = "agent_execution"
    AGENTEX_PLATFORM = "agentex_platform"


_BOUNDARY_CATEGORIES: dict[ErrorBoundary, ErrorCategory] = {
    ErrorBoundary.AGENT_EXECUTION: "application",
    ErrorBoundary.AGENTEX_PLATFORM: "platform",
}


def _normalize_module_prefix(value: str) -> str:
    normalized = value.strip().strip(".")
    if not normalized:
        raise ValueError("module ownership prefixes must be non-empty")
    return normalized


def _normalize_file_root(value: str) -> str:
    if not value or not os.path.isabs(value):
        raise ValueError("file ownership roots must be absolute")
    return os.path.normcase(os.path.normpath(value))


def _default_ignored_file_roots() -> tuple[str, ...]:
    roots = {
        _normalize_file_root(path)
        for key, path in sysconfig.get_paths().items()
        if key in {"stdlib", "platstdlib", "purelib", "platlib"} and path and os.path.isabs(path)
    }
    return tuple(sorted(roots))


_AGENTEX_PACKAGE_ROOT = _normalize_file_root(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)


@dataclass(frozen=True)
class TracebackOwnershipConfig:
    """Immutable rules for assigning traceback frames to an owner.

    Explicit module prefixes work for wheels, zip imports, and source trees.
    File roots support applications and editable/source checkouts. Frames under
    standard-library or site-package roots are ignored by default, except when
    an explicit application/platform rule owns them.
    """

    application_module_prefixes: tuple[str, ...] = ()
    platform_module_prefixes: tuple[str, ...] = ("agentex",)
    ignored_module_prefixes: tuple[str, ...] = ()
    application_file_roots: tuple[str, ...] = ()
    platform_file_roots: tuple[str, ...] = (_AGENTEX_PACKAGE_ROOT,)
    ignored_file_roots: tuple[str, ...] = _default_ignored_file_roots()
    infer_application_from_external_source: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "application_module_prefixes",
            tuple(_normalize_module_prefix(value) for value in self.application_module_prefixes),
        )
        object.__setattr__(
            self,
            "platform_module_prefixes",
            tuple(_normalize_module_prefix(value) for value in self.platform_module_prefixes),
        )
        object.__setattr__(
            self,
            "ignored_module_prefixes",
            tuple(_normalize_module_prefix(value) for value in self.ignored_module_prefixes),
        )
        object.__setattr__(
            self,
            "application_file_roots",
            tuple(_normalize_file_root(value) for value in self.application_file_roots),
        )
        object.__setattr__(
            self,
            "platform_file_roots",
            tuple(_normalize_file_root(value) for value in self.platform_file_roots),
        )
        object.__setattr__(
            self,
            "ignored_file_roots",
            tuple(_normalize_file_root(value) for value in self.ignored_file_roots),
        )


DEFAULT_TRACEBACK_OWNERSHIP_CONFIG = TracebackOwnershipConfig()


@dataclass(frozen=True)
class ExceptionMapping:
    """A narrowly scoped exception-to-owner mapping.

    ``scope`` is mandatory so broad exception types such as ``TimeoutError``
    cannot accidentally become global ownership rules. Subclasses are excluded
    unless ``include_subclasses`` is explicitly enabled.
    """

    scope: str
    exception_type: type[BaseException]
    category: ErrorCategory | str
    include_subclasses: bool = False

    def __post_init__(self) -> None:
        if not self.scope.strip():
            raise ValueError("exception mapping scope must be non-empty")
        if not isinstance(self.exception_type, type) or not issubclass(self.exception_type, BaseException):
            raise TypeError("exception_type must be a BaseException type")
        category = _normalize_error_category(self.category)
        if category not in ("application", "platform"):
            raise ValueError("exception mapping category must be 'application' or 'platform'")
        object.__setattr__(self, "scope", self.scope.strip())
        object.__setattr__(self, "category", category)


@dataclass(frozen=True)
class ErrorClassifierConfig:
    """Immutable stack and exception rules, safe to share across workers."""

    mappings: tuple[ExceptionMapping, ...] = ()
    traceback_ownership: TracebackOwnershipConfig = DEFAULT_TRACEBACK_OWNERSHIP_CONFIG

    def __init__(
        self,
        mappings: Sequence[ExceptionMapping] = (),
        *,
        traceback_ownership: TracebackOwnershipConfig = DEFAULT_TRACEBACK_OWNERSHIP_CONFIG,
    ) -> None:
        normalized = tuple(mappings)
        seen: set[tuple[str, type[BaseException]]] = set()
        for mapping in normalized:
            key = (mapping.scope, mapping.exception_type)
            if key in seen:
                raise ValueError(
                    f"duplicate exception mapping for scope={mapping.scope!r}, "
                    f"type={mapping.exception_type.__module__}.{mapping.exception_type.__qualname__}"
                )
            seen.add(key)
        object.__setattr__(self, "mappings", normalized)
        object.__setattr__(self, "traceback_ownership", traceback_ownership)


DEFAULT_ERROR_CLASSIFIER_CONFIG = ErrorClassifierConfig()


@dataclass(frozen=True)
class ErrorClassification:
    category: ErrorCategory
    source: ErrorCategorySource
    reason: str
    classifier_version: str = ERROR_CLASSIFIER_VERSION


def _normalize_error_category(value: object) -> ErrorCategory | None:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _ERROR_CATEGORIES:
            return cast(ErrorCategory, normalized)
    return None


def _module_matches(module_name: str | None, prefixes: tuple[str, ...]) -> bool:
    if module_name is None:
        return False
    return any(module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in prefixes)


def _path_is_under(filename: str, roots: tuple[str, ...]) -> bool:
    if not roots or not os.path.isabs(filename):
        return False
    normalized = os.path.normcase(os.path.normpath(filename))
    for root in roots:
        try:
            if os.path.commonpath((normalized, root)) == root:
                return True
        except ValueError:
            continue
    return False


def _is_archive_filename(filename: str) -> bool:
    normalized = filename.replace("\\", "/").lower()
    return any(marker in normalized for marker in (".zip/", ".whl/", ".pyz/"))


def _frame_ownership(
    traceback: TracebackType,
    config: TracebackOwnershipConfig,
) -> tuple[FrameOwnership, str]:
    module_value = traceback.tb_frame.f_globals.get("__name__")
    module_name = module_value if isinstance(module_value, str) else None
    filename = traceback.tb_frame.f_code.co_filename

    application_module = _module_matches(module_name, config.application_module_prefixes)
    platform_module = _module_matches(module_name, config.platform_module_prefixes)
    application_file = _path_is_under(filename, config.application_file_roots)
    platform_file = _path_is_under(filename, config.platform_file_roots)
    application_owned = application_module or application_file
    platform_owned = platform_module or platform_file

    if application_owned and platform_owned:
        return "ambiguous", "stack_ambiguous_owned_frame"
    if application_module:
        return "application", "application_module"
    if application_file:
        return "application", "application_file_root"
    if platform_module:
        return "platform", "platform_module"
    if platform_file:
        return "platform", "platform_file_root"

    if _module_matches(module_name, config.ignored_module_prefixes):
        return "ignored", "ignored_module"
    if _path_is_under(filename, config.ignored_file_roots):
        return "ignored", "ignored_file_root"

    if not filename or filename.startswith("<") or _is_archive_filename(filename):
        return "unresolved", "stack_unresolvable_frame"
    if config.infer_application_from_external_source and os.path.isabs(filename):
        return "application", "external_source_file"
    return "unresolved", "stack_unresolvable_frame"


def _stack_classification(
    exc: BaseException,
    config: TracebackOwnershipConfig,
) -> tuple[ErrorClassification | None, str]:
    traceback = exc.__traceback__
    if traceback is None:
        return None, "stack_no_traceback"

    frames: list[TracebackType] = []
    while traceback is not None:
        frames.append(traceback)
        traceback = traceback.tb_next

    for frame in reversed(frames):
        ownership, rule_id = _frame_ownership(frame, config)
        if ownership == "ignored":
            continue
        if ownership in ("ambiguous", "unresolved"):
            return None, rule_id
        return (
            ErrorClassification(
                category=cast(ErrorCategory, ownership),
                source="stack_trace",
                reason=f"stack_rule:{rule_id}",
            ),
            rule_id,
        )
    return None, "stack_no_owned_frame"


def _mapping_specificity(exc: BaseException, mapping: ExceptionMapping) -> tuple[int, str]:
    """Sort subclass mappings by nearest MRO type, then stable type name."""
    try:
        distance = type(exc).__mro__.index(mapping.exception_type)
    except ValueError:
        # ``isinstance`` can be true for virtual ABC subclasses absent from MRO.
        distance = len(type(exc).__mro__)
    exception_name = f"{mapping.exception_type.__module__}.{mapping.exception_type.__qualname__}"
    return distance, exception_name


def classify_error(
    exc: BaseException,
    explicit_category: ErrorCategory | str | None = None,
    *,
    boundary: ErrorBoundary | None = None,
    mapping_scope: str | None = None,
    classifier_config: ErrorClassifierConfig = DEFAULT_ERROR_CLASSIFIER_CONFIG,
) -> ErrorClassification:
    """Classify ownership without inspecting exception text or class names."""
    if explicit_category is not None:
        category = _normalize_error_category(explicit_category)
        if category is None:
            return ErrorClassification(
                category=ERROR_CATEGORY_UNKNOWN,
                source="explicit",
                reason="invalid_explicit_category",
            )
        return ErrorClassification(category=category, source="explicit", reason="caller_explicit_category")

    if isinstance(exc, CategorizedError):
        category = _normalize_error_category(exc.error_category)
        if category is None:
            return ErrorClassification(
                category=ERROR_CATEGORY_UNKNOWN,
                source="categorized_error",
                reason="invalid_canonical_category",
            )
        return ErrorClassification(category=category, source="categorized_error", reason="canonical_categorized_error")

    stack_classification, stack_failure_reason = _stack_classification(
        exc,
        classifier_config.traceback_ownership,
    )
    if stack_classification is not None:
        return stack_classification

    if boundary is not None:
        return ErrorClassification(
            category=_BOUNDARY_CATEGORIES[boundary],
            source="boundary",
            reason=f"agentex_boundary:{boundary.value}",
        )

    if mapping_scope is not None:
        exact_matches = [
            mapping
            for mapping in classifier_config.mappings
            if mapping.scope == mapping_scope and type(exc) is mapping.exception_type
        ]
        subclass_matches = [
            mapping
            for mapping in classifier_config.mappings
            if mapping.scope == mapping_scope
            and mapping.include_subclasses
            and isinstance(exc, mapping.exception_type)
            and type(exc) is not mapping.exception_type
        ]
        matches = exact_matches or sorted(
            subclass_matches,
            key=lambda mapping: _mapping_specificity(exc, mapping),
        )
        if matches:
            mapping = matches[0]
            exception_name = f"{mapping.exception_type.__module__}.{mapping.exception_type.__qualname__}"
            return ErrorClassification(
                category=cast(ErrorCategory, mapping.category),
                source="mapping",
                reason=f"registered_mapping:{exception_name}",
            )

    return ErrorClassification(
        category=ERROR_CATEGORY_UNKNOWN,
        source="fallback",
        reason=stack_failure_reason,
    )


def set_span_error(
    span: Span,
    exc: BaseException,
    *,
    error_category: ErrorCategory | str | None = None,
    boundary: ErrorBoundary | None = None,
    mapping_scope: str | None = None,
    classifier_config: ErrorClassifierConfig = DEFAULT_ERROR_CLASSIFIER_CONFIG,
) -> None:
    """Record an exception on ``span`` under ``data[SPAN_ERROR_KEY]``.

    Classification precedence is explicit category, canonical categorized
    exception, traceback inference, known Agentex boundary, scoped mapping,
    then unknown. The exception's own traceback is inspected automatically;
    callers never pass stack text or paths. The added keyword arguments
    preserve compatibility with existing callers.
    No-op when ``span.data`` is a list (matching ``_add_source_to_span``, which
    only attaches metadata to dict-shaped data).
    """
    classification = classify_error(
        exc,
        error_category,
        boundary=boundary,
        mapping_scope=mapping_scope,
        classifier_config=classifier_config,
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
