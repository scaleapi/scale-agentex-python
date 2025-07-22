import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer
from agentex.lib.types.acp import (
    CancelTaskParams,
    RPCMethod,
    SendEventParams,
)


class TestBaseACPServerInitialization:
    """Test BaseACPServer initialization and setup"""

    def test_base_acp_server_init(self):
        """Test BaseACPServer initialization sets up routes correctly"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            server = BaseACPServer()

            # Check that FastAPI routes are set up
            routes = [route.path for route in server.routes]
            assert "/healthz" in routes
            assert "/api" in routes

            # Check that handlers dict is initialized
            assert hasattr(server, "_handlers")
            assert isinstance(server._handlers, dict)

    def test_base_acp_server_create_classmethod(self):
        """Test BaseACPServer.create() class method"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            server = BaseACPServer.create()

            assert isinstance(server, BaseACPServer)
            assert hasattr(server, "_handlers")

    def test_lifespan_function_setup(self):
        """Test that lifespan function is properly configured"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            server = BaseACPServer()

            # Check that lifespan is configured
            assert server.router.lifespan_context is not None


class TestHealthCheckEndpoint:
    """Test health check endpoint functionality"""

    def test_health_check_endpoint(self, base_acp_server):
        """Test GET /healthz endpoint returns correct response"""
        client = TestClient(base_acp_server)

        response = client.get("/healthz")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_health_check_content_type(self, base_acp_server):
        """Test health check returns JSON content type"""
        client = TestClient(base_acp_server)

        response = client.get("/healthz")

        assert response.headers["content-type"] == "application/json"


class TestJSONRPCEndpointCore:
    """Test core JSON-RPC endpoint functionality"""

    def test_jsonrpc_endpoint_exists(self, base_acp_server):
        """Test POST /api endpoint exists"""
        client = TestClient(base_acp_server)

        # Send a basic request to check endpoint exists
        response = client.post("/api", json={})

        # Should not return 404 (endpoint exists)
        assert response.status_code != 404

    def test_jsonrpc_malformed_request(self, base_acp_server):
        """Test JSON-RPC endpoint handles malformed requests"""
        client = TestClient(base_acp_server)

        # Send malformed JSON
        response = client.post("/api", json={"invalid": "request"})

        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["jsonrpc"] == "2.0"

    def test_jsonrpc_method_not_found(self, base_acp_server):
        """Test JSON-RPC method not found error"""
        client = TestClient(base_acp_server)

        request = {
            "jsonrpc": "2.0",
            "method": "nonexistent/method",
            "params": {},
            "id": "test-1",
        }

        response = client.post("/api", json=request)

        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601  # Method not found
        assert data["id"] == "test-1"

    def test_jsonrpc_valid_request_structure(self, base_acp_server):
        """Test JSON-RPC request parsing with valid structure"""
        client = TestClient(base_acp_server)

        # Add a mock handler for testing
        async def mock_handler(params):
            return {"status": "success"}

        base_acp_server._handlers[RPCMethod.EVENT_SEND] = mock_handler

        request = {
            "jsonrpc": "2.0",
            "method": "event/send",
            "params": {
                "task": {"id": "test-task", "agent_id": "test-agent", "status": "RUNNING"},
                "message": {
                    "type": "text",
                    "author": "user",
                    "content": "test message",
                },
            },
            "id": "test-1",
        }

        response = client.post("/api", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == "test-1"
        print("DATA", data)
        # Should return immediate acknowledgment
        assert data["result"]["status"] == "processing"


class TestHandlerRegistration:
    """Test handler registration and management"""

    def test_on_task_event_send_decorator(self):
        """Test on_task_event_send decorator registration"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            server = BaseACPServer()

            @server.on_task_event_send
            async def test_handler(params: SendEventParams):
                return {"test": "response"}

            # Check handler is registered
            assert RPCMethod.EVENT_SEND in server._handlers
            assert server._handlers[RPCMethod.EVENT_SEND] is not None

    def test_cancel_task_decorator(self):
        """Test cancel_task decorator registration"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            server = BaseACPServer()

            @server.on_task_cancel
            async def test_handler(params: CancelTaskParams):
                return {"test": "response"}

            # Check handler is registered
            assert RPCMethod.TASK_CANCEL in server._handlers
            assert server._handlers[RPCMethod.TASK_CANCEL] is not None

    @pytest.mark.asyncio
    async def test_handler_wrapper_functionality(self):
        """Test that handler wrapper works correctly"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            server = BaseACPServer()

            # Create a test handler
            async def test_handler(params):
                return {"handler_called": True, "params_received": True}

            # Wrap the handler
            wrapped = server._wrap_handler(test_handler)

            # Test the wrapped handler
            result = await wrapped({"test": "params"})
            assert result["handler_called"] is True
            assert result["params_received"] is True


class TestBackgroundProcessing:
    """Test background processing functionality"""

    @pytest.mark.asyncio
    async def test_notification_processing(self, async_base_acp_server):
        """Test notification processing (requests with no ID)"""
        # Add a mock handler
        handler_called = False
        received_params = None

        async def mock_handler(params):
            nonlocal handler_called, received_params
            handler_called = True
            received_params = params
            return {"status": "processed"}

        async_base_acp_server._handlers[RPCMethod.EVENT_SEND] = mock_handler

        client = TestClient(async_base_acp_server)

        request = {
            "jsonrpc": "2.0",
            "method": "event/send",
            "params": {
                "task": {"id": "test-task", "agent_id": "test-agent", "status": "RUNNING"},
                "message": {
                    "type": "text",
                    "author": "user",
                    "content": "test message",
                },
            },
            # No ID = notification
        }

        response = client.post("/api", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] is None  # Notification response

        # Give background task time to execute
        await asyncio.sleep(0.1)

        # Handler should have been called
        assert handler_called is True
        assert received_params is not None

    @pytest.mark.asyncio
    async def test_request_processing_with_id(self, async_base_acp_server):
        """Test request processing with ID returns immediate acknowledgment"""

        # Add a mock handler
        async def mock_handler(params):
            return {"status": "processed"}

        async_base_acp_server._handlers[RPCMethod.TASK_CANCEL] = mock_handler

        client = TestClient(async_base_acp_server)

        request = {
            "jsonrpc": "2.0",
            "method": "task/cancel",
            "params": {"task_id": "test-task-123"},
            "id": "test-request-1",
        }

        response = client.post("/api", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == "test-request-1"
        assert data["result"]["status"] == "processing"  # Immediate acknowledgment


class TestSynchronousRPCMethods:
    """Test synchronous RPC methods that return results immediately"""

    def test_send_message_synchronous_response(self, base_acp_server):
        """Test that MESSAGE_SEND method returns handler result synchronously"""
        client = TestClient(base_acp_server)

        # Add a mock handler that returns a specific result
        async def mock_execute_handler(params):
            return {
                "task_id": params.task.id,
                "message_content": params.message.content,
                "status": "executed_synchronously",
                "custom_data": {"processed": True, "timestamp": "2024-01-01T12:00:00Z"},
            }

        base_acp_server._handlers[RPCMethod.MESSAGE_SEND] = mock_execute_handler

        request = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "task": {"id": "test-task-123", "agent_id": "test-agent", "status": "RUNNING"},
                "message": {
                    "type": "text",
                    "author": "user",
                    "content": "Execute this task please",
                },
            },
            "id": "test-execute-1",
        }

        response = client.post("/api", json=request)

        assert response.status_code == 200
        data = response.json()

        # Verify JSON-RPC structure
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == "test-execute-1"
        assert "result" in data
        assert data.get("error") is None

        # Verify the handler's result is returned directly (not "processing" status)
        result = data["result"]
        assert result["task_id"] == "test-task-123"
        assert result["message_content"] == "Execute this task please"
        assert result["status"] == "executed_synchronously"
        assert result["custom_data"]["processed"] is True
        assert result["custom_data"]["timestamp"] == "2024-01-01T12:00:00Z"

        # Verify it's NOT the async "processing" response
        assert result.get("status") != "processing"

    def test_create_task_async_response(self, base_acp_server):
        """Test that TASK_CREATE method returns processing status (async behavior)"""
        client = TestClient(base_acp_server)

        # Add a mock handler for init task
        async def mock_init_handler(params):
            return {
                "task_id": params.task.id,
                "status": "initialized",
            }

        base_acp_server._handlers[RPCMethod.TASK_CREATE] = mock_init_handler

        request = {
            "jsonrpc": "2.0",
            "method": "task/create",
            "params": {
                "task": {"id": "test-task-456", "agent_id": "test-agent", "status": "RUNNING"}
            },
            "id": "test-init-1",
        }

        response = client.post("/api", json=request)

        assert response.status_code == 200
        data = response.json()

        # Verify JSON-RPC structure
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == "test-init-1"
        assert "result" in data
        assert data.get("error") is None

        # Verify it returns async "processing" status (not the handler's result)
        result = data["result"]
        assert result["status"] == "processing"

        # Verify it's NOT the handler's actual result
        assert result.get("status") != "initialized"


class TestErrorHandling:
    """Test error handling scenarios"""

    def test_invalid_json_request(self, base_acp_server):
        """Test handling of invalid JSON in request body"""
        client = TestClient(base_acp_server)

        # Send invalid JSON
        response = client.post(
            "/api", content="invalid json", headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["jsonrpc"] == "2.0"

    def test_missing_required_fields(self, base_acp_server):
        """Test handling of requests missing required JSON-RPC fields"""
        client = TestClient(base_acp_server)

        # Missing method field
        request = {"jsonrpc": "2.0", "params": {}, "id": "test-1"}

        response = client.post("/api", json=request)

        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_invalid_method_enum(self, base_acp_server):
        """Test handling of invalid method names"""
        client = TestClient(base_acp_server)

        request = {
            "jsonrpc": "2.0",
            "method": "invalid/method/name",
            "params": {},
            "id": "test-1",
        }

        response = client.post("/api", json=request)

        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601  # Method not found

    @pytest.mark.asyncio
    async def test_handler_exception_handling(self, async_base_acp_server):
        """Test that handler exceptions are properly handled"""

        # Add a handler that raises an exception
        async def failing_handler(params):
            raise ValueError("Test exception")

        async_base_acp_server._handlers[RPCMethod.EVENT_SEND] = failing_handler

        client = TestClient(async_base_acp_server)

        request = {
            "jsonrpc": "2.0",
            "method": "event/send",
            "params": {
                "task": {"id": "test-task", "agent_id": "test-agent", "status": "RUNNING"},
                "message": {
                    "type": "text",
                    "author": "user",
                    "content": "test message",
                },
            },
            "id": "test-1",
        }

        response = client.post("/api", json=request)

        # Should still return immediate acknowledgment
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["status"] == "processing"

        # Give background task time to fail
        await asyncio.sleep(0.1)
        # Exception should be logged but not crash the server
