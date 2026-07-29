"""End-to-end propagation of the caller-supplied ``end_user_id`` onto spans.

Three legs: the protocol field itself, the sync ACP server binding it at the
JSON-RPC choke point, and the Temporal ACP server forwarding it into the workflow
start args and event signal payload for the baggage interceptor to pick up.
"""

from __future__ import annotations

from typing import Any, override
from unittest.mock import Mock, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from agentex.types.task import Task
from agentex.types.agent import Agent
from agentex.types.event import Event
from agentex.protocol.acp import (
    RPCMethod,
    SendEventParams,
    CancelTaskParams,
    CreateTaskParams,
    SendMessageParams,
    InterruptTaskParams,
)
from agentex.lib.core.tracing.trace import Trace
from agentex.lib.core.tracing.baggage import END_USER_ID_SPAN_KEY, get_end_user_id
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.types.task_message_content import TextContent
from agentex.lib.sdk.fastacp.impl.temporal_acp import TemporalACP
from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer
from agentex.lib.core.temporal.services.temporal_task_service import TemporalTaskService


def _agent() -> Agent:
    return Agent(
        id="agent-1",
        name="test-agent",
        description="test agent",
        acp_type="async",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def _task() -> Task:
    return Task(id="task-1", status="RUNNING")


def _event() -> Event:
    return Event(
        id="event-1",
        agent_id="agent-1",
        task_id="task-1",
        sequence_id=1,
        content=TextContent(author="user", content="hi"),
    )


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class TestProtocol:
    @pytest.mark.parametrize(
        "model,kwargs",
        [
            (CreateTaskParams, {}),
            (SendMessageParams, {"content": TextContent(author="user", content="hi")}),
            (SendEventParams, {"event": _event()}),
            (CancelTaskParams, {}),
        ],
    )
    def test_field_is_accepted(self, model: type, kwargs: dict[str, Any]) -> None:
        params = model(agent=_agent(), task=_task(), end_user_id="user-1", **kwargs)
        assert params.end_user_id == "user-1"

    @pytest.mark.parametrize(
        "model,kwargs",
        [
            (CreateTaskParams, {}),
            (SendMessageParams, {"content": TextContent(author="user", content="hi")}),
            (SendEventParams, {"event": _event()}),
            (CancelTaskParams, {}),
        ],
    )
    def test_field_is_optional(self, model: type, kwargs: dict[str, Any]) -> None:
        """Older control planes omit it entirely."""
        params = model(agent=_agent(), task=_task(), **kwargs)
        assert params.end_user_id is None

    def test_interrupt_does_not_carry_it(self) -> None:
        """task/interrupt has no end_user_id on the control plane either."""
        assert "end_user_id" not in InterruptTaskParams.model_fields


# ---------------------------------------------------------------------------
# Sync agents
# ---------------------------------------------------------------------------


_observed_span_data: list[Any] = []


class _SpanCreatingServer(BaseACPServer):
    """Creates a span inside the handler, exactly as an agent's own code would."""

    __test__ = False

    @override
    def _setup_handlers(self) -> None:
        @self.on_message_send
        async def handler(params: SendMessageParams) -> TextContent:  # type: ignore[reportUnusedFunction]
            trace = Trace(processors=[], client=MagicMock(), trace_id="trace-1")
            span = trace.start_span(name="work")
            _observed_span_data.append(span.data)
            return TextContent(author="agent", content=str(get_end_user_id()))


def _message_send_request(end_user_id: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "agent": {
            "id": "agent-1",
            "name": "test-agent",
            "description": "d",
            "acp_type": "sync",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        },
        "task": {"id": "task-1"},
        "content": {"type": "text", "author": "user", "content": "hi"},
        "stream": False,
    }
    if end_user_id is not None:
        params["end_user_id"] = end_user_id
    return {"jsonrpc": "2.0", "method": RPCMethod.MESSAGE_SEND.value, "params": params, "id": 1}


class TestSyncAgentPropagation:
    @pytest.fixture(autouse=True)
    def _reset_observed(self):
        _observed_span_data.clear()
        yield
        _observed_span_data.clear()

    def test_span_created_in_the_handler_is_stamped(self) -> None:
        client = TestClient(_SpanCreatingServer.create())

        response = client.post("/api", json=_message_send_request("user-1"))

        assert response.status_code == 200
        assert _observed_span_data == [{END_USER_ID_SPAN_KEY: "user-1"}]

    def test_handler_sees_the_value_in_context(self) -> None:
        client = TestClient(_SpanCreatingServer.create())

        response = client.post("/api", json=_message_send_request("user-1"))

        assert response.json()["result"]["content"]["content"] == "user-1"

    def test_nothing_is_stamped_when_the_caller_omits_it(self) -> None:
        client = TestClient(_SpanCreatingServer.create())

        response = client.post("/api", json=_message_send_request(None))

        assert response.status_code == 200
        assert _observed_span_data == [None]

    def test_one_request_does_not_bleed_into_the_next(self) -> None:
        """The failure mode this whole design exists to avoid."""
        client = TestClient(_SpanCreatingServer.create())

        client.post("/api", json=_message_send_request("user-a"))
        client.post("/api", json=_message_send_request(None))

        assert _observed_span_data == [{END_USER_ID_SPAN_KEY: "user-a"}, None]


# ---------------------------------------------------------------------------
# Temporal agents
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_temporal_client() -> AsyncMock:
    client = AsyncMock()
    client.start_workflow = AsyncMock(return_value="workflow-1")
    client.send_signal = AsyncMock(return_value=None)
    return client


@pytest.fixture
def task_service(mock_temporal_client: AsyncMock) -> TemporalTaskService:
    env_vars = Mock(spec=EnvironmentVariables)
    env_vars.WORKFLOW_NAME = "test-workflow"
    env_vars.WORKFLOW_TASK_QUEUE = "test-queue"
    env_vars.WORKFLOW_EXECUTION_TIMEOUT_SECONDS = None
    return TemporalTaskService(temporal_client=mock_temporal_client, env_vars=env_vars)


class TestTemporalPropagation:
    async def test_submit_task_puts_it_in_the_workflow_start_args(
        self, task_service: TemporalTaskService, mock_temporal_client: AsyncMock
    ) -> None:
        await task_service.submit_task(agent=_agent(), task=_task(), params=None, end_user_id="user-1")

        arg = mock_temporal_client.start_workflow.call_args.kwargs["arg"]
        assert arg.end_user_id == "user-1"

    async def test_submit_task_defaults_to_none(
        self, task_service: TemporalTaskService, mock_temporal_client: AsyncMock
    ) -> None:
        await task_service.submit_task(agent=_agent(), task=_task(), params=None)

        arg = mock_temporal_client.start_workflow.call_args.kwargs["arg"]
        assert arg.end_user_id is None

    async def test_send_event_puts_it_in_the_signal_payload(
        self, task_service: TemporalTaskService, mock_temporal_client: AsyncMock
    ) -> None:
        await task_service.send_event(agent=_agent(), task=_task(), event=_event(), end_user_id="user-1")

        payload = mock_temporal_client.send_signal.call_args.kwargs["payload"]
        assert payload["end_user_id"] == "user-1"

    async def test_acp_task_create_handler_forwards_it(
        self, task_service: TemporalTaskService, mock_temporal_client: AsyncMock
    ) -> None:
        acp = TemporalACP(temporal_address="localhost:7233", temporal_task_service=task_service)
        acp._setup_handlers()

        handler = acp._handlers[RPCMethod.TASK_CREATE]
        assert handler is not None
        await handler(CreateTaskParams(agent=_agent(), task=_task(), end_user_id="user-1"))

        arg = mock_temporal_client.start_workflow.call_args.kwargs["arg"]
        assert arg.end_user_id == "user-1"

    async def test_acp_event_send_handler_forwards_it(
        self, task_service: TemporalTaskService, mock_temporal_client: AsyncMock
    ) -> None:
        acp = TemporalACP(temporal_address="localhost:7233", temporal_task_service=task_service)
        acp._setup_handlers()

        handler = acp._handlers[RPCMethod.EVENT_SEND]
        assert handler is not None
        await handler(SendEventParams(agent=_agent(), task=_task(), event=_event(), end_user_id="user-1"))

        payload = mock_temporal_client.send_signal.call_args.kwargs["payload"]
        assert payload["end_user_id"] == "user-1"
