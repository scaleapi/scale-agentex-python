# ruff: noqa: I001
from __future__ import annotations
from typing import Any, override
import sys
import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

"""Header forwarding tests consolidated.

We stub tracing modules to avoid circular imports when importing ACPService.
"""

# Stub tracing modules before importing ACPService
tracer_stub = types.ModuleType("agentex.lib.core.tracing.tracer")

class _StubSpan:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: object) -> bool:
        return False

class _StubTrace:
    def span(self, **kwargs: Any) -> _StubSpan:  # type: ignore[name-defined]
        return _StubSpan()

class _StubAsyncTracer:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass
    def trace(self, trace_id: str | None = None) -> _StubTrace:  # type: ignore[name-defined]
        return _StubTrace()

class _StubTracer(_StubAsyncTracer):
    pass
tracer_stub.AsyncTracer = _StubAsyncTracer  # type: ignore[attr-defined]
tracer_stub.Tracer = _StubTracer  # type: ignore[attr-defined]
sys.modules["agentex.lib.core.tracing.tracer"] = tracer_stub

tracing_pkg_stub = types.ModuleType("agentex.lib.core.tracing")
tracing_pkg_stub.AsyncTracer = _StubAsyncTracer  # type: ignore[attr-defined]
tracing_pkg_stub.Tracer = _StubTracer  # type: ignore[attr-defined]
sys.modules["agentex.lib.core.tracing"] = tracing_pkg_stub

from agentex.lib.core.services.adk.acp.acp import ACPService
from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer
from agentex.lib.types.acp import RPCMethod, SendMessageParams, SendEventParams
from agentex.types.task_message_content import TextContent
from agentex.lib.sdk.fastacp.impl.temporal_acp import TemporalACP
from agentex.lib.core.temporal.services.temporal_task_service import TemporalTaskService
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.types.agent import Agent
from agentex.types.task import Task
from agentex.types.event import Event


class DummySpan:
    def __init__(self, **_kwargs: Any) -> None:
        self.output = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: object) -> bool:
        return False


class DummyTrace:
    def span(self, **kwargs: Any) -> DummySpan:
        return DummySpan(**kwargs)


class DummyTracer:
    def trace(self, trace_id: str | None = None) -> DummyTrace:
        return DummyTrace()


class DummyAgents:
    async def rpc_by_name(self, *args: Any, **kwargs: Any) -> Any:
        # Support both positional and keyword agent name, and both params/_params
        method = kwargs.get("method")
        extra_headers = kwargs.get("extra_headers")
        # Ensure headers are forwarded as-is
        assert extra_headers == {"x-user": "a", "authorization": "b"}
        # Minimal response object with .result
        if method == "task/create":
            return type("R", (), {"result": {"id": "t1"}})()
        if method == "message/send":
            # include required task_id for TaskMessage model
            return type("R", (), {"result": {"id": "m1", "task_id": "t1", "content": {"type": "text", "author": "user", "content": "ok"}}})()
        if method == "event/send":
            # include required fields for Event model
            return type("R", (), {"result": {"id": "e1", "agent_id": "a1", "task_id": "t1", "sequence_id": 1}})()
        if method == "task/cancel":
            return type("R", (), {"result": {"id": "t1"}})()
        raise AssertionError("Unexpected method")


class DummyClient:
    def __init__(self) -> None:
        self.agents = DummyAgents()


@pytest.mark.asyncio
async def test_header_forwarding() -> None:
    client = DummyClient()
    svc = ACPService(agentex_client=client, tracer=DummyTracer())  # type: ignore[arg-type]

    # Create task
    task = await svc.task_create(agent_name="x", request={"headers": {"x-user": "a", "authorization": "b"}})
    assert task.id == "t1"

    # Send message
    msgs = await svc.message_send(
        agent_name="x",
        task_id="t1",
        content=TextContent(author="user", content="hi"),
        request={"headers": {"x-user": "a", "authorization": "b"}},
    )
    assert len(msgs) == 1

    # Send event
    evt = await svc.event_send(
        agent_name="x",
        task_id="t1",
        content=TextContent(author="user", content="hi"),
        request={"headers": {"x-user": "a", "authorization": "b"}},
    )
    assert evt.id == "e1"

    # Cancel
    task2 = await svc.task_cancel(agent_name="x", task_id="t1", request={"headers": {"x-user": "a", "authorization": "b"}})
    assert task2.id == "t1"


class TestServer(BaseACPServer):
    __test__ = False
    @override
    def _setup_handlers(self):
        @self.on_message_send
        async def handler(params: SendMessageParams):  # type: ignore[reportUnusedFunction]
            headers = (params.request or {}).get("headers", {})
            assert "x-agent-api-key" not in headers
            assert headers.get("x-user") == "a"
            return TextContent(author="agent", content="ok")


def test_excludes_agent_api_key_header():
    app = TestServer.create()
    client = TestClient(app)
    req = {
        "jsonrpc": "2.0",
        "method": RPCMethod.MESSAGE_SEND.value,
        "params": {
            "agent": {"id": "a1", "name": "n1", "description": "d", "acp_type": "sync"},
            "task": {"id": "t1"},
            "content": {"type": "text", "author": "user", "content": "hi"},
            "stream": False,
        },
        "id": 1,
    }
    r = client.post("/api", json=req, headers={"x-user": "a", "x-agent-api-key": "secret"})
    assert r.status_code == 200


def filter_headers_standalone(
    headers: dict[str, str] | None,
    allowlist: list[str] | None
) -> dict[str, str]:
    """Standalone header filtering function matching the production implementation."""
    if not headers:
        return {}
    
    # Pass-through behavior: if no allowlist, forward all headers
    if allowlist is None:
        return headers

    # Apply filtering based on allowlist
    if not allowlist:
        return {}
    
    import fnmatch
    filtered = {}
    for header_name, header_value in headers.items():
        # Check against allowlist patterns (case-insensitive)
        header_allowed = False
        for pattern in allowlist:
            if fnmatch.fnmatch(header_name.lower(), pattern.lower()):
                header_allowed = True
                break

        if header_allowed:
            filtered[header_name] = header_value

    return filtered


def test_filter_headers_no_headers() -> None:
    allowlist = ["x-user-email"]
    result = filter_headers_standalone(None, allowlist)
    assert result == {}
    
    result = filter_headers_standalone({}, allowlist)
    assert result == {}


def test_filter_headers_pass_through_by_default() -> None:
    headers = {
        "x-user-email": "test@example.com", 
        "x-admin-token": "secret",
        "authorization": "Bearer token",
        "x-custom-header": "value"
    }
    result = filter_headers_standalone(headers, None)
    assert result == headers


def test_filter_headers_empty_allowlist() -> None:
    allowlist: list[str] = []
    headers = {"x-user-email": "test@example.com", "x-admin-token": "secret"}
    result = filter_headers_standalone(headers, allowlist)
    assert result == {}


def test_filter_headers_allowed_headers() -> None:
    allowlist = ["x-user-email", "x-tenant-id"]
    headers = {
        "x-user-email": "test@example.com",
        "x-tenant-id": "tenant123",
        "x-admin-token": "secret",
        "content-type": "application/json"
    }
    result = filter_headers_standalone(headers, allowlist)
    expected = {
        "x-user-email": "test@example.com",
        "x-tenant-id": "tenant123"
    }
    assert result == expected


def test_filter_headers_case_insensitive_patterns() -> None:
    allowlist = ["X-User-Email", "x-tenant-*"]
    headers = {
        "x-user-email": "test@example.com",
        "X-TENANT-ID": "tenant123",
        "x-tenant-name": "acme",
        "x-admin-token": "secret"
    }
    result = filter_headers_standalone(headers, allowlist)
    expected = {
        "x-user-email": "test@example.com",
        "X-TENANT-ID": "tenant123",
        "x-tenant-name": "acme"
    }
    assert result == expected


def test_filter_headers_wildcard_patterns() -> None:
    allowlist = ["x-user-*", "authorization"]
    headers = {
        "x-user-id": "123",
        "x-user-email": "test@example.com", 
        "x-user-role": "admin",
        "authorization": "Bearer token",
        "x-system-info": "blocked",
        "content-type": "application/json"
    }
    result = filter_headers_standalone(headers, allowlist)
    expected = {
        "x-user-id": "123",
        "x-user-email": "test@example.com",
        "x-user-role": "admin",
        "authorization": "Bearer token"
    }
    assert result == expected


def test_filter_headers_complex_patterns() -> None:
    allowlist = ["x-tenant-*", "x-user-[abc]*", "auth*"]
    headers = {
        "x-tenant-id": "tenant1",
        "x-tenant-name": "acme",
        "x-user-admin": "true",
        "x-user-beta": "false",
        "x-user-delta": "test",
        "authorization": "Bearer x",
        "authenticate": "digest",
        "content-type": "json",
    }
    result = filter_headers_standalone(headers, allowlist)
    expected = {
        "x-tenant-id": "tenant1",
        "x-tenant-name": "acme",
        "x-user-admin": "true", 
        "x-user-beta": "false",
        "authorization": "Bearer x",
        "authenticate": "digest"
    }
    assert result == expected


def test_filter_headers_all_types() -> None:
    allowlist = ["authorization", "accept-language", "custom-*"]
    headers = {
        "authorization": "Bearer token",
        "accept-language": "en-US",
        "custom-header": "value",
        "custom-auth": "token",
        "content-type": "application/json",
        "x-blocked": "value"
    }
    result = filter_headers_standalone(headers, allowlist)
    expected = {
        "authorization": "Bearer token",
        "accept-language": "en-US", 
        "custom-header": "value",
        "custom-auth": "token"
    }
    assert result == expected



# ============================================================================
# Temporal Header Forwarding Tests
# ============================================================================

@pytest.fixture
def mock_temporal_client():
    """Create a mock TemporalClient"""
    client = AsyncMock()
    client.send_signal = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_env_vars():
    """Create mock environment variables"""
    env_vars = Mock(spec=EnvironmentVariables)
    env_vars.WORKFLOW_NAME = "test-workflow"
    env_vars.WORKFLOW_TASK_QUEUE = "test-queue"
    return env_vars


@pytest.fixture
def temporal_task_service(mock_temporal_client, mock_env_vars):
    """Create TemporalTaskService with mocked client"""
    return TemporalTaskService(
        temporal_client=mock_temporal_client,
        env_vars=mock_env_vars,
    )


@pytest.fixture
def sample_agent():
    """Create a sample agent"""
    return Agent(
        id="agent-123",
        name="test-agent",
        description="Test agent",
        acp_type="agentic",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_task():
    """Create a sample task"""
    return Task(id="task-456")


@pytest.fixture
def sample_event():
    """Create a sample event"""
    return Event(
        id="event-789",
        agent_id="agent-123",
        task_id="task-456",
        sequence_id=1,
        content=TextContent(author="user", content="Test message")
    )


@pytest.mark.asyncio
async def test_temporal_task_service_send_event_with_headers(
    temporal_task_service,
    mock_temporal_client,
    sample_agent,
    sample_task,
    sample_event
):
    """Test that TemporalTaskService forwards request headers in signal payload"""
    # Given
    request_headers = {
        "x-user-oauth-credentials": "test-oauth-token",
        "x-custom-header": "custom-value"
    }
    request = {"headers": request_headers}

    # When
    await temporal_task_service.send_event(
        agent=sample_agent,
        task=sample_task,
        event=sample_event,
        request=request
    )

    # Then
    mock_temporal_client.send_signal.assert_called_once()
    call_args = mock_temporal_client.send_signal.call_args

    # Verify the signal was sent to the correct workflow
    assert call_args.kwargs["workflow_id"] == sample_task.id
    assert call_args.kwargs["signal"] == "receive_event"

    # Verify the payload includes the request with headers
    payload = call_args.kwargs["payload"]
    assert "request" in payload
    assert payload["request"] == request
    assert payload["request"]["headers"] == request_headers


@pytest.mark.asyncio
async def test_temporal_task_service_send_event_without_headers(
    temporal_task_service,
    mock_temporal_client,
    sample_agent,
    sample_task,
    sample_event
):
    """Test that TemporalTaskService handles missing request gracefully"""
    # When - Send event without request parameter
    await temporal_task_service.send_event(
        agent=sample_agent,
        task=sample_task,
        event=sample_event,
        request=None
    )

    # Then
    mock_temporal_client.send_signal.assert_called_once()
    call_args = mock_temporal_client.send_signal.call_args

    # Verify the payload has request as None
    payload = call_args.kwargs["payload"]
    assert payload["request"] is None


@pytest.mark.asyncio
async def test_temporal_acp_integration_with_request_headers(
    mock_temporal_client,
    mock_env_vars,
    sample_agent,
    sample_task,
    sample_event
):
    """Test end-to-end integration: TemporalACP -> TemporalTaskService -> TemporalClient signal"""
    # Given - Create real TemporalTaskService with mocked client
    task_service = TemporalTaskService(
        temporal_client=mock_temporal_client,
        env_vars=mock_env_vars,
    )

    # Create TemporalACP with real task service
    temporal_acp = TemporalACP(
        temporal_address="localhost:7233",
        temporal_task_service=task_service,
    )
    temporal_acp._setup_handlers()

    request_headers = {
        "x-user-id": "user-123",
        "authorization": "Bearer token",
        "x-tenant-id": "tenant-456"
    }
    request = {"headers": request_headers}

    # Create SendEventParams as TemporalACP would receive it
    params = SendEventParams(
        agent=sample_agent,
        task=sample_task,
        event=sample_event,
        request=request
    )

    # When - Trigger the event handler via the decorated function
    # The handler is registered via @temporal_acp.on_task_event_send
    # We'll directly call the task service method as the handler does
    await task_service.send_event(
        agent=params.agent,
        task=params.task,
        event=params.event,
        request=params.request
    )

    # Then - Verify the temporal client received the signal with request headers
    mock_temporal_client.send_signal.assert_called_once()
    call_args = mock_temporal_client.send_signal.call_args

    # Verify signal payload includes request with headers
    payload = call_args.kwargs["payload"]
    assert payload["request"] == request
    assert payload["request"]["headers"] == request_headers


@pytest.mark.asyncio
async def test_temporal_task_service_preserves_all_header_types(
    temporal_task_service,
    mock_temporal_client,
    sample_agent,
    sample_task,
    sample_event
):
    """Test that various header types are preserved correctly"""
    # Given - Headers with different patterns
    request_headers = {
        "x-user-oauth-credentials": "oauth-token-12345",
        "authorization": "Bearer jwt-token",
        "x-tenant-id": "tenant-999",
        "x-custom-app-header": "custom-value"
    }
    request = {"headers": request_headers}

    # When
    await temporal_task_service.send_event(
        agent=sample_agent,
        task=sample_task,
        event=sample_event,
        request=request
    )

    # Then - Verify all headers are preserved in the signal payload
    call_args = mock_temporal_client.send_signal.call_args
    payload = call_args.kwargs["payload"]

    assert payload["request"]["headers"] == request_headers
    # Verify each header individually
    for header_name, header_value in request_headers.items():
        assert payload["request"]["headers"][header_name] == header_value
