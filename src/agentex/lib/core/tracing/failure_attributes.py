"""Span attributes the offline failure checks read, written and validated from one spec.

The SGP processor ships ``span.data`` verbatim as span metadata, so each attribute is a flat
dotted key holding a native JSON value. The output schema is written as JSON text instead, since
the span store would spread a schema object into many paths whose keys can collide.
"""

from __future__ import annotations

import re
import json
from typing import Any, Literal, Callable, cast
from dataclasses import field, dataclass
from collections.abc import Sequence

__all__ = (
    "REQUIRED_OUTPUTS_KEY",
    "STEP_BUDGET_KEY",
    "STOP_REASON_KEY",
    "OUTPUT_NAME_KEY",
    "VERIFICATION_KEY",
    "ESCALATION_CHANNELS_KEY",
    "VERIFICATION_RESULT_KEY",
    "ESCALATES_KEY",
    "OUTPUT_SCHEMA_KEY",
    "QUOTE_ARGUMENTS_KEY",
    "PROMPT_VERSION_KEY",
    "VerificationRule",
    "FailureCheckSpec",
    "output_name",
    "verification_result",
    "escalates",
)

REQUIRED_OUTPUTS_KEY = "sgp.agent.required_outputs"
STEP_BUDGET_KEY = "sgp.agent.step_budget"
STOP_REASON_KEY = "sgp.agent.stop_reason"
OUTPUT_NAME_KEY = "sgp.agent.output_name"
VERIFICATION_KEY = "sgp.agent.verification"
ESCALATION_CHANNELS_KEY = "sgp.agent.escalation_channels"
VERIFICATION_RESULT_KEY = "sgp.agent.verification_result"
ESCALATES_KEY = "sgp.agent.escalates"
OUTPUT_SCHEMA_KEY = "sgp.agent.output_schema"
QUOTE_ARGUMENTS_KEY = "sgp.agent.quote_arguments"
PROMPT_VERSION_KEY = "sgp.agent.prompt_version"

# Exactly one dot: OpenAI tool names cannot contain dots, so this is a tool and one top-level argument.
_TOOL_ARGUMENT_RE = re.compile(r"[^.\s]+\.[^.\s]+")
_VERIFICATION_RESULTS: tuple[str, ...] = ("pass", "fail")


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a non-empty string, got {value!r}")
    if value != value.strip():
        raise ValueError(f"{what} must not have leading or trailing whitespace, got {value!r}")
    return value


def _unique_texts(values: object, what: str) -> tuple[str, ...]:
    if not isinstance(values, Sequence) or isinstance(values, str | bytes):
        raise ValueError(f"{what} must be a list of strings, got {values!r}")
    items = tuple(_text(item, f"{what} entry") for item in values)
    seen: set[str] = set()
    for item in items:
        if item in seen:
            raise ValueError(f"{what} has a duplicate entry {item!r}")
        seen.add(item)
    return items


def _tool_arguments(values: object, what: str) -> tuple[str, ...]:
    items = _unique_texts(values, what)
    for item in items:
        if _TOOL_ARGUMENT_RE.fullmatch(item) is None:
            hint = ", nested argument paths are not supported" if item.count(".") > 1 else ""
            raise ValueError(f"{what} entry must look like tool.argument{hint}, got {item!r}")
    return items


def _step_budget(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"step_budget must be a positive integer, got {value!r}")
    return value


def _require_string_keys(value: object, what: str) -> None:
    # Iterative, so a very deep schema is rejected by the encoder in _json_object instead of overflowing the stack here.
    pending: list[object] = [value]
    seen: set[int] = set()
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            if id(node) in seen:
                continue
            seen.add(id(node))
            for key, child in cast("dict[object, object]", node).items():
                if not isinstance(key, str):
                    raise ValueError(f"{what} keys must be strings, got {key!r}")
                pending.append(child)
        elif isinstance(node, list | tuple):
            if id(node) in seen:
                continue
            seen.add(id(node))
            pending.extend(cast("Sequence[object]", node))


def _json_object(value: object, what: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{what} must be a JSON object (a dict), got {type(value).__name__}")
    _require_string_keys(value, what)
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError(f"{what} must be JSON serializable: {exc}") from exc


@dataclass(frozen=True)
class VerificationRule:
    """A verification step and the name of what it verifies."""

    step: str
    verifies: str

    def __post_init__(self) -> None:
        _text(self.step, "verification step")
        _text(self.verifies, "verification verifies")


def _rules(values: object) -> tuple[VerificationRule, ...]:
    if not isinstance(values, Sequence) or isinstance(values, str | bytes):
        raise ValueError(f"verification must be a list of VerificationRule, got {values!r}")
    for rule in values:
        if not isinstance(rule, VerificationRule):
            raise ValueError(f"verification entries must be VerificationRule, got {rule!r}")
    rules = tuple(values)
    if len(set(rules)) != len(rules):
        raise ValueError("verification has a duplicate rule")
    return rules


_NORMALIZERS: dict[str, Callable[[Any], Any]] = {
    "required_outputs": lambda v: _unique_texts(v, "required_outputs"),
    "step_budget": _step_budget,
    "stop_reason": lambda v: _text(v, "stop_reason"),
    "verification": _rules,
    "escalation_channels": lambda v: _tool_arguments(v, "escalation_channels"),
    "output_schema": lambda v: _json_object(v, "output_schema"),
    "quote_arguments": lambda v: _tool_arguments(v, "quote_arguments"),
    "prompt_version": lambda v: _text(v, "prompt_version"),
}


def _listed(values: Sequence[str] | None) -> list[str] | None:
    return None if values is None else list(values)


@dataclass(frozen=True, kw_only=True)
class FailureCheckSpec:
    """Declarations for the root span. None leaves one undeclared and an empty list declares none."""

    required_outputs: Sequence[str] | None = None
    step_budget: int | None = None
    stop_reason: str | None = None
    verification: Sequence[VerificationRule] | None = None
    escalation_channels: Sequence[str] | None = None
    output_schema: dict[str, Any] | None = field(default=None, hash=False)
    quote_arguments: Sequence[str] | None = None
    prompt_version: str | None = None

    def __post_init__(self) -> None:
        for name, normalize in _NORMALIZERS.items():
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, normalize(value))

    def attributes(self) -> dict[str, Any]:
        """The root span data, holding only the declared attributes."""
        declared: dict[str, Any] = {
            REQUIRED_OUTPUTS_KEY: _listed(self.required_outputs),
            STEP_BUDGET_KEY: self.step_budget,
            STOP_REASON_KEY: self.stop_reason,
            VERIFICATION_KEY: None
            if self.verification is None
            else [{"step": rule.step, "verifies": rule.verifies} for rule in self.verification],
            ESCALATION_CHANNELS_KEY: _listed(self.escalation_channels),
            # The stored dict can be edited after construction, so check it again before writing it.
            OUTPUT_SCHEMA_KEY: None
            if self.output_schema is None
            else json.dumps(_json_object(self.output_schema, "output_schema"), separators=(",", ":")),
            QUOTE_ARGUMENTS_KEY: _listed(self.quote_arguments),
            PROMPT_VERSION_KEY: self.prompt_version,
        }
        return {key: value for key, value in declared.items() if value is not None}


def output_name(name: str) -> dict[str, str]:
    """Data for the span that produces a required output."""
    return {OUTPUT_NAME_KEY: _text(name, "output name")}


def verification_result(result: Literal["pass", "fail"]) -> dict[str, str]:
    """Data for a verification span."""
    if result not in _VERIFICATION_RESULTS:
        raise ValueError(f"verification result must be 'pass' or 'fail', got {result!r}")
    return {VERIFICATION_RESULT_KEY: result}


def escalates(*verification_span_ids: str) -> dict[str, list[str]]:
    """Data for an escalation span, naming every verification span it escalates."""
    if not verification_span_ids:
        raise ValueError("escalates needs at least one verification span id")
    return {ESCALATES_KEY: list(_unique_texts(verification_span_ids, "escalates verification span id"))}
