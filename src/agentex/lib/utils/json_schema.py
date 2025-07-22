from typing import Any

import jsonref
from jsonschema import validate as schema_validation


def resolve_refs(schema: dict) -> dict:
    """
    Resolve JSON references in a schema.
    """
    resolved = jsonref.replace_refs(schema, proxies=False, lazy_load=False)
    serializable = {
        "type": resolved.get("type"),
        "properties": resolved.get("properties"),
        "required": list(resolved.get("required", [])),
        "additionalProperties": resolved.get("additionalProperties", False),
    }
    return serializable


def validate_payload(json_schema: dict[str, Any], payload: dict[str, Any]) -> None:
    """Validate the payload against the JSON schema."""
    schema_validation(instance=payload, schema=json_schema)
