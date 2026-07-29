"""Request-scoped identifiers that the framework stamps onto trace spans.

The tracing processors cannot read per-request context: they run on a long-lived
queue-drain task whose contextvars were frozen when the first span in the process
was enqueued (see ``span_queue.py``). So per-request values have to be attached to
the ``Span`` object *before* it is enqueued, travelling with it as data rather than
as ambient context.

Deliberately one reserved, size-capped scalar rather than an arbitrary dict, which
keeps caller-controlled free-form data (and its PHI and cardinality risks) off the
tracing backend.
"""

from __future__ import annotations

from typing import Any, TypeVar
from contextvars import Token, ContextVar

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

# Matches the ``__key__`` style the SGP processor stamps its static keys with.
END_USER_ID_SPAN_KEY = "__end_user_id__"
# Mirrors the cap the control plane enforces on the RPC field.
END_USER_ID_MAX_LENGTH = 256

_end_user_id: ContextVar[str | None] = ContextVar("agentex_end_user_id", default=None)


def set_end_user_id(value: str | None) -> Token[str | None]:
    """Bind the end user for the current context, returning a reset token.

    Normalized here rather than at the merge point, so a span never carries
    something the backend would reject.
    """
    normalized: str | None = None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            normalized = stripped[:END_USER_ID_MAX_LENGTH]
            if len(stripped) > END_USER_ID_MAX_LENGTH:
                logger.warning(f"Truncated end_user_id from {len(stripped)} to {END_USER_ID_MAX_LENGTH} characters")
    return _end_user_id.set(normalized)


def get_end_user_id() -> str | None:
    return _end_user_id.get()


def reset_end_user_id(token: Token[str | None]) -> None:
    _end_user_id.reset(token)


def get_baggage() -> dict[str, str]:
    """The span data keys to stamp for the current context."""
    end_user_id = _end_user_id.get()
    if end_user_id is None:
        return {}
    return {END_USER_ID_SPAN_KEY: end_user_id}


DataT = TypeVar("DataT")


def merge_baggage_into_span_data(data: DataT) -> DataT | dict[str, Any]:
    """Merge the current context's baggage into already-serialized span data.

    Explicit call-site data wins on collision. Span data may also be a list, which
    has nowhere to put a key, so those are returned untouched.
    """
    baggage = get_baggage()
    if not baggage:
        return data
    if data is None:
        return dict(baggage)
    if not isinstance(data, dict):
        logger.debug(f"Skipping trace baggage merge for span data of type {type(data).__name__}")
        return data
    return {**baggage, **data}
