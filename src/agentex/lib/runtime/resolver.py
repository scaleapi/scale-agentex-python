from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from agentex.lib.runtime.models import Credentials

HEADER_ACTING_USER_API_KEY = "x-acting-user-api-key"
HEADER_ACTING_AS_AGENT = "x-acting-as-agent"
SGP_TARGET = "sgp"
ENV_SGP_API_KEY = "SGP_API_KEY"


def _normalize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key.lower(): value for key, value in headers.items()}


@runtime_checkable
class CredentialResolver(Protocol):
    """Plugin interface for resolving outbound credentials by target name."""

    async def resolve(
        self,
        headers: dict[str, str],
        agent_id: str,
        target: str,
    ) -> Credentials:
        """Return credentials for the given target using inbound request context."""
        ...


class PassthroughResolver:
    """Default resolver: forwarded user API key, then legacy SGP_API_KEY fallback."""

    async def resolve(
        self,
        headers: dict[str, str],
        agent_id: str,
        target: str,
    ) -> Credentials:
        del agent_id  # reserved for future per-agent resolution (OBO, vault lookups)

        normalized = _normalize_headers(headers)
        api_key = normalized.get(HEADER_ACTING_USER_API_KEY) or os.environ.get(ENV_SGP_API_KEY)
        if not api_key:
            raise RuntimeError(
                "No credential available for target "
                f"'{target}': expected inbound header "
                f"'{HEADER_ACTING_USER_API_KEY}' or environment variable "
                f"'{ENV_SGP_API_KEY}'."
            )

        if target == SGP_TARGET:
            return Credentials(scheme="api_key", value=api_key)

        # v1 passthrough uses the same user API key shape for all targets.
        return Credentials(scheme="bearer", value=api_key)
