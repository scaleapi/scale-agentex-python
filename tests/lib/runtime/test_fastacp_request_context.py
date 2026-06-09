from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from agentex.lib.runtime import current_request
from agentex.lib.runtime.resolver import SGP_TARGET, HEADER_ACTING_USER_API_KEY
from agentex.types.task_message_update import StreamTaskMessageFull
from agentex.types.task_message_content import TextContent
from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer


def _message_send_request(*, stream: bool = False) -> dict:
    return {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "agent": {
                "id": "agent-123",
                "name": "test-agent",
                "description": "test-agent",
                "acp_type": "sync",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
            },
            "task": {"id": "task-123", "status": "RUNNING"},
            "content": {"type": "text", "author": "user", "content": "hello"},
            "stream": stream,
        },
        "id": "req-1",
    }


class TestRequestContextIntegration:
    def test_message_send_handler_can_read_forwarded_credentials(self) -> None:
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            server = BaseACPServer()
            observed: dict[str, str] = {}

            @server.on_message_send
            async def handler(params):
                context = current_request()
                credentials = await context.get_credentials_for(SGP_TARGET)
                observed["agent_id"] = context.agent_id
                observed["credential"] = credentials.value
                return TextContent(type="text", author="agent", content="ok")

            client = TestClient(server)
            response = client.post(
                "/api",
                json=_message_send_request(),
                headers={HEADER_ACTING_USER_API_KEY: "delegated-user-key"},
            )

            assert response.status_code == 200
            assert observed["agent_id"] == "agent-123"
            assert observed["credential"] == "delegated-user-key"

    def test_streaming_handler_keeps_request_context_active(self) -> None:
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            server = BaseACPServer()
            observed: list[str] = []

            @server.on_message_send
            async def handler(params):
                token = await current_request().get_token(SGP_TARGET)
                observed.append(token)
                yield StreamTaskMessageFull(
                    type="full",
                    index=0,
                    content=TextContent(type="text", author="agent", content="ok"),
                )

            client = TestClient(server)
            response = client.post(
                "/api",
                json=_message_send_request(stream=True),
                headers={HEADER_ACTING_USER_API_KEY: "stream-user-key"},
            )

            # Consume the NDJSON stream so the wrapped generator runs to completion.
            assert response.status_code == 200
            assert response.text
            assert observed == ["stream-user-key"]
