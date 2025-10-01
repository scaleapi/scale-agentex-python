# ruff: noqa: I001
from typing import Any, override
import sys
import types

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
from agentex.lib.types.acp import RPCMethod, SendMessageParams
from agentex.types.task_message_content import TextContent


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


