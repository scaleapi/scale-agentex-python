"""Tests for StateService forwarding task_id/agent_id to the SDK client.

Regression guard for the 0.13.0 incident: the generated client dropped
task_id/agent_id from states.update(), so the ADK stopped sending them in the
body and every state write 422'd against backends predating scale-agentex#278.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock

from agentex.types.state import State
from agentex.lib.core.services.adk.state import StateService

_TS = datetime(2026, 5, 13, 18, 30, 0, tzinfo=timezone.utc)


def _make_state() -> State:
    return State(
        id="s1",
        agent_id="a1",
        task_id="t1",
        state={"k": "v"},
        created_at=_TS,
    )


def _mock_span():
    span = Mock()
    span.output = None

    async def __aenter__(_self):
        return span

    async def __aexit__(_self, *args):
        return None

    span.__aenter__ = __aenter__
    span.__aexit__ = __aexit__
    return span


def _make_service() -> tuple[AsyncMock, StateService]:
    client = AsyncMock()
    tracer = Mock()
    trace = Mock()
    trace.span.return_value = _mock_span()
    tracer.trace.return_value = trace
    return client, StateService(agentex_client=client, tracer=tracer)


class TestUpdateStateSendsParentIdentifiers:
    async def test_task_id_and_agent_id_sent_in_body(self) -> None:
        client, svc = _make_service()
        client.states.update.return_value = _make_state()

        await svc.update_state(
            state_id="s1",
            task_id="t1",
            agent_id="a1",
            state={"k": "v"},
        )

        kwargs = client.states.update.call_args.kwargs
        assert kwargs["state_id"] == "s1"
        # task_id/agent_id must ride in extra_body — the generated client dropped
        # them from the typed signature, but old backends still require them.
        assert kwargs["extra_body"] == {"task_id": "t1", "agent_id": "a1"}
