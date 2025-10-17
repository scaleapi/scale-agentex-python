from __future__ import annotations

from typing import Any

import jsonref
from jsonschema import validate as schema_validation


def resolve_refs(schema: dict) -> dict:
    """
    Resolve JSON references in a schema.
    """
    resolved = jsonref.replace_refs(schema, proxies=False, lazy_load=False)
    serializable = {
        "type": resolved.get("type"),  # type: ignore[union-attr]
        "properties": resolved.get("properties"),  # type: ignore[union-attr]
        "required": list(resolved.get("required", [])),  # type: ignore[union-attr]
        "additionalProperties": resolved.get("additionalProperties", False),  # type: ignore[union-attr]
    }
    return serializable


def validate_payload(json_schema: dict[str, Any], payload: dict[str, Any]) -> None:
    """Validate the payload against the JSON schema."""
    schema_validation(instance=payload, schema=json_schema)
