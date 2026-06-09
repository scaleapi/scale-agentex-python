from __future__ import annotations

import pytest

from agentex.lib.runtime import (
    PassthroughResolver,
)
from agentex.lib.runtime.resolver import SGP_TARGET, HEADER_ACTING_USER_API_KEY


@pytest.fixture
def resolver() -> PassthroughResolver:
    return PassthroughResolver()


@pytest.mark.asyncio
async def test_passthrough_resolver_prefers_forwarded_api_key(
    resolver: PassthroughResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SGP_API_KEY", "legacy-key")

    credentials = await resolver.resolve(
        {HEADER_ACTING_USER_API_KEY: "user-key"},
        agent_id="agent-1",
        target=SGP_TARGET,
    )

    assert credentials.scheme == "api_key"
    assert credentials.value == "user-key"


@pytest.mark.asyncio
async def test_passthrough_resolver_falls_back_to_env(
    resolver: PassthroughResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SGP_API_KEY", "legacy-key")

    credentials = await resolver.resolve({}, agent_id="agent-1", target=SGP_TARGET)

    assert credentials.value == "legacy-key"


@pytest.mark.asyncio
async def test_passthrough_resolver_raises_when_missing(
    resolver: PassthroughResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SGP_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match=HEADER_ACTING_USER_API_KEY):
        await resolver.resolve({}, agent_id="agent-1", target=SGP_TARGET)


@pytest.mark.asyncio
async def test_passthrough_resolver_normalizes_header_case(
    resolver: PassthroughResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SGP_API_KEY", raising=False)

    credentials = await resolver.resolve(
        {"X-Acting-User-Api-Key": "user-key"},
        agent_id="agent-1",
        target=SGP_TARGET,
    )

    assert credentials.value == "user-key"


@pytest.mark.asyncio
async def test_passthrough_resolver_non_sgp_target_returns_bearer(
    resolver: PassthroughResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SGP_API_KEY", "legacy-key")

    credentials = await resolver.resolve({}, agent_id="agent-1", target="slack")

    assert credentials.scheme == "bearer"
    assert credentials.value == "legacy-key"
