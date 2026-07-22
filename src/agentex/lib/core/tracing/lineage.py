"""Data-source reference capture for lineage: tools declare which sources they
touch and the refs land in span data under the ``sgp.lineage.refs`` key."""

from __future__ import annotations

import re
import json
from typing import Any, Literal, Callable, Iterable

from pydantic import Field, BaseModel, field_validator

try:
    from agentex.lib.utils.logging import make_logger

    logger = make_logger(__name__)
except Exception:  # ddtrace may be absent in some envs; fall back to stdlib
    import logging

    logger = logging.getLogger(__name__)

LINEAGE_REFS_KEY = "sgp.lineage.refs"

# The URI arm of the lineage namespace identifier rule (namespace-conventions.md):
# lowercase scheme and host (dots/hyphens only — normalize `_` to `-`), one optional path segment.
_URI_NAMESPACE_RE = re.compile(r"^[a-z][a-z0-9._-]*://[a-z0-9.-]+(/[a-zA-Z0-9._-]*)?$")

RefResolver = Callable[[dict[str, Any]], "list[DataSourceRef]"]


class DataSourceRef(BaseModel):
    """One data source a tool call touched, as a lineage coordinate."""

    namespace: str = Field(max_length=512)
    name: str = Field(min_length=1, max_length=512)
    version: str | None = Field(default=None, max_length=256)
    role: Literal["input", "output"] = "input"

    def __init__(self, namespace: str | None = None, name: str | None = None, **kwargs: Any) -> None:
        if namespace is not None:
            kwargs["namespace"] = namespace
        if name is not None:
            kwargs["name"] = name
        super().__init__(**kwargs)

    @field_validator("namespace")
    @classmethod
    def _namespace_is_uri_form(cls, value: str) -> str:
        if not _URI_NAMESPACE_RE.match(value):
            raise ValueError(f"namespace must be URI-form (scheme://system), got: {value!r}")
        return value


class _ToolSources(BaseModel):
    refs: list[DataSourceRef] = Field(default_factory=list)
    resolver: RefResolver | None = None

    model_config = {"arbitrary_types_allowed": True}


_tool_sources: dict[str, _ToolSources] = {}


def register_tool_sources(
    tool_name: str,
    refs: Iterable[DataSourceRef] | None = None,
    resolver: RefResolver | None = None,
) -> None:
    """Declare the data sources a tool touches, keyed by its tool name.

    Use for tools the agent does not own (e.g. MCP proxy tools). Static refs and
    a resolver over the tool's parsed arguments may be combined; repeated
    registration for the same name replaces the prior entry. The registry is
    process-wide: co-located agents sharing a tool name share (and overwrite)
    one entry, so disambiguate shared names before co-locating agent types.
    """
    _tool_sources[tool_name] = _ToolSources(refs=list(refs or []), resolver=resolver)


def data_sources(*refs: DataSourceRef, resolver: RefResolver | None = None) -> Callable[[Any], Any]:
    """Decorator form of ``register_tool_sources`` for tools the agent owns.

    Works below or above ``@function_tool``: the tool name is taken from the
    decorated object's ``name`` attribute when present, else ``__name__``.
    """

    def _register(obj: Any) -> Any:
        tool_name = getattr(obj, "name", None) or getattr(obj, "__name__", None)
        if isinstance(tool_name, str) and tool_name:
            register_tool_sources(tool_name, refs=refs, resolver=resolver)
        else:
            logger.warning("data_sources could not determine a tool name for %r; refs not registered", obj)
        return obj

    return _register


def clear_tool_sources() -> None:
    """Reset the registry (test isolation)."""
    _tool_sources.clear()


def resolve_refs(tool_name: str, arguments: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Resolve registered refs for one tool call to serialized, deduplicated dicts.

    Resolver failures are logged and swallowed: ref capture must never break a
    tool call or its tracing.
    """
    entry = _tool_sources.get(tool_name)
    if entry is None:
        return []
    refs = list(entry.refs)
    if entry.resolver is not None:
        try:
            refs.extend(entry.resolver(arguments or {}))
        except Exception:
            logger.warning("data-source resolver for tool %s failed; static refs kept", tool_name, exc_info=True)
    return _dedupe(refs)


def resolve_refs_from_items(items: Iterable[Any]) -> list[dict[str, Any]]:
    """Resolve refs across serialized run items, matching ``function_call`` entries.

    Accepts the item dicts the providers already build for span output; string
    ``arguments`` are parsed as JSON for resolver-based registrations.
    """
    refs: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "function_call":
            continue
        tool_name = item.get("name")
        if not isinstance(tool_name, str) or not tool_name:
            continue
        arguments = item.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except (ValueError, TypeError):
                arguments = {}
        refs.extend(resolve_refs(tool_name, arguments if isinstance(arguments, dict) else {}))
    return _dedupe_dicts(refs)


def record(span: Any, refs: Iterable[DataSourceRef]) -> None:
    """Attach refs to a manually managed span (no-op when the span is None)."""
    if span is None:
        return
    merged = merge_refs_into_data(getattr(span, "data", None), _dedupe(list(refs)))
    span.data = merged


def merge_refs_into_data(data: dict[str, Any] | None, refs: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge serialized refs into a span data dict, deduplicating with any present."""
    out = dict(data) if isinstance(data, dict) else {}
    if refs:
        existing = out.get(LINEAGE_REFS_KEY)
        combined = list(existing) if isinstance(existing, list) else []
        combined.extend(refs)
        out[LINEAGE_REFS_KEY] = _dedupe_dicts(combined)
    return out


def _dedupe(refs: list[DataSourceRef]) -> list[dict[str, Any]]:
    return _dedupe_dicts([ref.model_dump(exclude_none=True) for ref in refs])


def _dedupe_dicts(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    out: list[dict[str, Any]] = []
    for ref in refs:
        key = (ref.get("namespace"), ref.get("name"), ref.get("version"), ref.get("role"))
        if key not in seen:
            seen.add(key)
            out.append(ref)
    return out
