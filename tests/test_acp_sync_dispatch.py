"""Unit tests for synchronous dispatch of ``task/create`` and ``event/send``.

Background dispatch of these two methods loses work silently. The ACP server
used to answer ``{"status": "processing"}`` before running the handler, so a
caller doing ``task/create`` then ``event/send`` could have its signal reach
Temporal before the workflow existed. The signal was dropped with
``workflow not found``, and the caller saw success either way because the
handler's exception was raised into a background task that only logged it.

These tests pin the two properties that fix depends on:

1. The response is not sent until the handler has finished, so a caller that
   sequences two calls gets the ordering it asked for.
2. A handler that raises produces a JSON-RPC error, so the failure is visible
   and retryable at the client.

``SyncACP`` is used as the transport because it constructs with no Temporal
connection and no network, and the dispatch under test lives in the shared
``BaseACPServer``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.protocol.acp import (
    RPC_SYNC_METHODS,
    RPCMethod,
    SendEventParams,
    CreateTaskParams,
)
from agentex.protocol.json_rpc import JSONRPCResponse
from agentex.lib.sdk.fastacp.impl.sync_acp import SyncACP


def _agent() -> Agent:
    return Agent(
        id="test-agent-456",
        name="test-agent",
        description="test-agent",
        acp_type="async",
        created_at="2023-01-01T00:00:00Z",
        updated_at="2023-01-01T00:00:00Z",
    )


def _task() -> Task:
    return Task(id="test-task-123", status="RUNNING")


def _event() -> Event:
    return Event(
        id="test-event-789",
        agent_id="test-agent-456",
        sequence_id=1,
        task_id="test-task-123",
    )


class _FakeRequest:
    """The slice of ``starlette.requests.Request`` that ``_handle_jsonrpc`` uses."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.headers: dict[str, str] = {}

    async def json(self) -> dict[str, Any]:
        return self._payload


async def _dispatch(acp: SyncACP, method: RPCMethod, params: Any) -> JSONRPCResponse:
    """Call the JSON-RPC entry point and narrow its untyped return."""
    response = await acp._handle_jsonrpc(_FakeRequest(_rpc(method, params)))  # pyright: ignore[reportArgumentType]
    assert isinstance(response, JSONRPCResponse)
    return response


def _rpc(method: RPCMethod, params: Any) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "method": method.value,
        "params": params.model_dump(mode="json"),
        "id": f"{method.value}-test",
    }


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class TestSyncMethodSet:
    @pytest.mark.parametrize(
        "method",
        [RPCMethod.MESSAGE_SEND, RPCMethod.TASK_CREATE, RPCMethod.EVENT_SEND],
    )
    def test_method_is_synchronous(self, method: RPCMethod) -> None:
        assert method in RPC_SYNC_METHODS


# ---------------------------------------------------------------------------
# Dispatch ordering
# ---------------------------------------------------------------------------


class TestHandlerCompletesBeforeResponse:
    async def test_task_create_awaits_handler(self) -> None:
        acp = SyncACP()
        order: list[str] = []

        @acp.on_task_create
        async def handler(params: CreateTaskParams) -> None:
            # Yield control so a backgrounded handler would lose the race and
            # let the response be sent first.
            await asyncio.sleep(0)
            order.append("handler")

        response = await _dispatch(acp, RPCMethod.TASK_CREATE, CreateTaskParams(agent=_agent(), task=_task()))
        order.append("response")

        assert order == ["handler", "response"]
        assert response.error is None
        assert response.result != {"status": "processing"}

    async def test_event_send_awaits_handler(self) -> None:
        acp = SyncACP()
        order: list[str] = []

        @acp.on_task_event_send
        async def handler(params: SendEventParams) -> None:
            await asyncio.sleep(0)
            order.append("handler")

        response = await _dispatch(
            acp, RPCMethod.EVENT_SEND, SendEventParams(agent=_agent(), task=_task(), event=_event())
        )
        order.append("response")

        assert order == ["handler", "response"]
        assert response.error is None
        assert response.result != {"status": "processing"}


# ---------------------------------------------------------------------------
# Failure visibility
# ---------------------------------------------------------------------------


class TestHandlerFailureReachesCaller:
    async def test_task_create_failure_returns_error(self) -> None:
        acp = SyncACP()

        @acp.on_task_create
        async def handler(params: CreateTaskParams) -> None:
            raise RuntimeError("workflow not found for ID: test-task-123")

        response = await _dispatch(acp, RPCMethod.TASK_CREATE, CreateTaskParams(agent=_agent(), task=_task()))

        assert response.error is not None
        assert "workflow not found" in response.error.message

    async def test_event_send_failure_returns_error(self) -> None:
        acp = SyncACP()

        @acp.on_task_event_send
        async def handler(params: SendEventParams) -> None:
            raise RuntimeError("workflow not found for ID: test-task-123")

        response = await _dispatch(
            acp, RPCMethod.EVENT_SEND, SendEventParams(agent=_agent(), task=_task(), event=_event())
        )

        assert response.error is not None
        assert "workflow not found" in response.error.message
