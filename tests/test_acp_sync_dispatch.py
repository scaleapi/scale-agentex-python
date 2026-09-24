"""Unit tests for the dispatch mode of ``task/create`` and ``event/send``.

``task/create`` hands back an id for a task that now exists, and its handler is
what starts the Temporal workflow. Dispatching it in the background answered
before the handler ran, so the id named a workflow the server could not yet
route to. A caller that followed ``task/create`` with ``event/send`` could have
its signal arrive first and be dropped with ``workflow not found``, and it saw
success either way because the handler's exception was raised into a background
task that only logged it.

``event/send`` keeps its background dispatch on purpose: callers send events in
quick succession and the workflow drains them as a batch, which awaiting each
send would serialise. These tests pin both halves so neither is changed by
accident:

1. ``task/create`` finishes its handler before responding, and surfaces a
   handler failure as a JSON-RPC error.
2. ``event/send`` still acknowledges immediately without waiting.

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


def _create_params() -> CreateTaskParams:
    return CreateTaskParams(agent=_agent(), task=_task(), params=None)


def _event_params() -> SendEventParams:
    return SendEventParams(agent=_agent(), task=_task(), event=_event())


class _FakeRequest:
    """The slice of ``starlette.requests.Request`` that ``_handle_jsonrpc`` uses."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.headers: dict[str, str] = {}

    async def json(self) -> dict[str, Any]:
        return self._payload


def _rpc(method: RPCMethod, params: Any) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "method": method.value,
        "params": params.model_dump(mode="json"),
        "id": f"{method.value}-test",
    }


async def _dispatch(acp: SyncACP, method: RPCMethod, params: Any) -> JSONRPCResponse:
    """Call the JSON-RPC entry point and narrow its untyped return."""
    response = await acp._handle_jsonrpc(_FakeRequest(_rpc(method, params)))  # pyright: ignore[reportArgumentType]
    assert isinstance(response, JSONRPCResponse)
    return response


# ---------------------------------------------------------------------------
# Which methods are synchronous
# ---------------------------------------------------------------------------


class TestSyncMethodSet:
    @pytest.mark.parametrize("method", [RPCMethod.MESSAGE_SEND, RPCMethod.TASK_CREATE])
    def test_method_is_synchronous(self, method: RPCMethod) -> None:
        assert method in RPC_SYNC_METHODS

    def test_event_send_stays_asynchronous(self) -> None:
        # Batching depends on it: callers send events in quick succession and the
        # workflow drains them together. Awaiting each send serialises them.
        assert RPCMethod.EVENT_SEND not in RPC_SYNC_METHODS


# ---------------------------------------------------------------------------
# task/create: handler completes before the response
# ---------------------------------------------------------------------------


class TestTaskCreateAwaitsHandler:
    async def test_handler_runs_before_response(self) -> None:
        acp = SyncACP()
        order: list[str] = []

        @acp.on_task_create
        async def handler(params: CreateTaskParams) -> None:
            # Yield control so a backgrounded handler would lose the race and
            # let the response be sent first.
            await asyncio.sleep(0)
            order.append("handler")

        response = await _dispatch(acp, RPCMethod.TASK_CREATE, _create_params())
        order.append("response")

        assert order == ["handler", "response"]
        assert response.error is None
        assert response.result != {"status": "processing"}

    async def test_handler_failure_returns_error(self) -> None:
        acp = SyncACP()

        @acp.on_task_create
        async def handler(params: CreateTaskParams) -> None:
            raise RuntimeError("workflow not found for ID: test-task-123")

        response = await _dispatch(acp, RPCMethod.TASK_CREATE, _create_params())

        assert response.error is not None
        assert "workflow not found" in response.error.message


# ---------------------------------------------------------------------------
# event/send: acknowledges without waiting
# ---------------------------------------------------------------------------


class TestEventSendIsBackgrounded:
    async def test_response_does_not_wait_for_handler(self) -> None:
        acp = SyncACP()
        started = asyncio.Event()
        order: list[str] = []

        @acp.on_task_event_send
        async def handler(params: SendEventParams) -> None:
            await asyncio.sleep(0)
            order.append("handler")
            started.set()

        response = await _dispatch(acp, RPCMethod.EVENT_SEND, _event_params())
        order.append("response")

        # The acknowledgment comes back before the handler has run, which is what
        # lets a caller enqueue several events without waiting on each one.
        assert order == ["response"]
        assert response.result == {"status": "processing"}

        # The handler still runs, just afterwards.
        await asyncio.wait_for(started.wait(), timeout=5)
        assert order == ["response", "handler"]
