"""Helpers for the platform's JSON-encoded metadata filter query parameters.

The containment filters on ``agents.list(agent_card_metadata=...)`` and
``tasks.list(task_metadata=...)`` carry their filter as a JSON-encoded object
inside a single query string value, so the generated clients type them as
``str``. Encoding by hand is easy to get subtly wrong -- Python's ``json``
happily emits ``NaN``/``Infinity``, which the server rejects with a 400 -- so
these helpers do it once, here, in the hand-written layer where they survive
SDK regeneration.

    from agentex.lib.utils.metadata_filters import encode_metadata_filter

    client.agents.list(
        agent_card_metadata=encode_metadata_filter({"permits_capable": True}),
    )
"""

from __future__ import annotations

import json
from typing import Any, Mapping

__all__ = ["encode_metadata_filter"]


def encode_metadata_filter(metadata: Mapping[str, Any]) -> str:
    """Encode a metadata filter mapping into the wire form the platform expects.

    Args:
        metadata: The key/value pairs the target's metadata object must contain.
            Values may be any JSON type; matching is exact containment, so
            ``{"permits_capable": True}`` matches a stored JSON ``true`` but not
            the string ``"true"``. An empty mapping matches any target that has
            a metadata object at all.

    Returns:
        A compact JSON object string, with keys sorted so the same filter always
        produces the same query value.

    Raises:
        TypeError: If ``metadata`` is not a mapping, or contains a value that
            isn't JSON-serializable.
        ValueError: If a value is a non-finite float. ``NaN`` and ``Infinity``
            aren't valid JSON and the server rejects them with a 400, so fail
            here with a clearer message instead.
    """
    if not isinstance(metadata, Mapping):
        raise TypeError(f"metadata must be a mapping, got {type(metadata).__name__}")

    try:
        return json.dumps(metadata, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except ValueError as exc:
        raise ValueError(f"metadata filter is not encodable as JSON: {exc}") from exc
