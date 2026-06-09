from __future__ import annotations

import pytest

from agentex.lib.runtime import (
    PassthroughResolver,
    current_request,
    request_context_scope,
)
from agentex.lib.runtime.resolver import SGP_TARGET, HEADER_ACTING_USER_API_KEY


@pytest.mark.asyncio
async def test_current_request_exposes_credentials() -> None:
    async with request_context_scope(
        {HEADER_ACTING_USER_API_KEY: "user-key"},
        agent_id="agent-123",
        resolver=PassthroughResolver(),
    ):
        context = current_request()
        credentials = await context.get_credentials_for(SGP_TARGET)
        token = await context.get_token(SGP_TARGET)

    assert context.agent_id == "agent-123"
    assert credentials.value == "user-key"
    assert token == "user-key"


@pytest.mark.asyncio
async def test_current_request_outside_scope_raises() -> None:
    with pytest.raises(RuntimeError, match="No active Agentex request context"):
        current_request()


@pytest.mark.asyncio
async def test_request_context_scope_resets_after_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SGP_API_KEY", "legacy-key")

    async with request_context_scope({}, agent_id="agent-123"):
        assert current_request().agent_id == "agent-123"

    with pytest.raises(RuntimeError, match="No active Agentex request context"):
        current_request()
