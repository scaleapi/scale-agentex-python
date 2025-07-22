import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from agentex.lib.sdk.fastacp.impl.agentic_base_acp import AgenticBaseACP
from agentex.lib.sdk.fastacp.impl.sync_acp import SyncACP
from agentex.lib.sdk.fastacp.impl.temporal_acp import TemporalACP
from agentex.lib.types.acp import (
    CancelTaskParams,
    CreateTaskParams,
    RPCMethod,
    SendEventParams,
)


class TestImplementationBehavior:
    """Test specific behavior differences between ACP implementations"""

    @pytest.mark.asyncio()
    async def test_sync_acp_default_handlers(self):
        """Test SyncACP has expected default handlers"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            sync_acp = SyncACP.create()

            # Should have send_message_message handler by default
            assert RPCMethod.MESSAGE_SEND in sync_acp._handlers

    @pytest.mark.asyncio()
    async def test_agentic_acp_default_handlers(self):
        """Test AgenticBaseACP has expected default handlers"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            agentic_acp = AgenticBaseACP.create()

            # Should have create, message, and cancel handlers by default
            assert RPCMethod.TASK_CREATE in agentic_acp._handlers
            assert RPCMethod.EVENT_SEND in agentic_acp._handlers
            assert RPCMethod.TASK_CANCEL in agentic_acp._handlers

    @pytest.mark.asyncio()
    async def test_temporal_acp_creation_with_mocked_client(self):
        """Test TemporalACP creation with mocked temporal client"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            with patch.object(TemporalACP, "create", new_callable=AsyncMock) as mock_create:
                mock_temporal_instance = MagicMock(spec=TemporalACP)
                mock_temporal_instance._handlers = {}
                mock_temporal_instance.temporal_client = MagicMock()
                mock_create.return_value = mock_temporal_instance

                temporal_acp = await TemporalACP.create()

                assert temporal_acp == mock_temporal_instance
                assert hasattr(temporal_acp, "temporal_client")


class TestRealWorldScenarios:
    """Test real-world usage scenarios and integration"""

    @pytest.mark.asyncio()
    async def test_message_handling_workflow(self, sync_acp, free_port, test_server_runner):
        """Test complete message handling workflow"""
        messages_received = []

        @sync_acp.on_task_event_send
        async def message_handler(params: SendEventParams):
            messages_received.append(
                {
                    "task_id": params.task.id,
                    "message_content": params.message.content,
                    "author": params.message.author,
                }
            )
            return {"processed": True}

        runner = test_server_runner(sync_acp, free_port)
        await runner.start()

        # Send multiple messages
        async with httpx.AsyncClient() as client:
            for i in range(3):
                request_data = {
                    "jsonrpc": "2.0",
                    "method": "event/send",
                    "params": {
                        "task": {
                            "id": f"workflow-task-{i}",
                            "agent_id": "workflow-agent",
                            "status": "RUNNING",
                        },
                        "message": {
                            "type": "text",
                            "author": "user",
                            "content": f"Workflow message {i}",
                        },
                    },
                    "id": f"workflow-{i}",
                }

                response = await client.post(f"http://127.0.0.1:{free_port}/api", json=request_data)
                assert response.status_code == 200

        # Give background tasks time to process
        await asyncio.sleep(0.2)

        # Verify all messages were processed
        assert len(messages_received) == 3
        for i, msg in enumerate(messages_received):
            assert msg["task_id"] == f"workflow-task-{i}"
            assert msg["message_content"] == f"Workflow message {i}"
            assert msg["author"] == "user"

        await runner.stop()

    @pytest.mark.asyncio()
    async def test_task_lifecycle_management(self, agentic_base_acp, free_port, test_server_runner):
        """Test complete task lifecycle: create -> message -> cancel"""
        task_events = []

        @agentic_base_acp.on_task_create
        async def create_handler(params: CreateTaskParams):
            task_events.append(("created", params.task.id))

        @agentic_base_acp.on_task_event_send
        async def message_handler(params: SendEventParams):
            task_events.append(("message", params.task.id))

        @agentic_base_acp.on_task_cancel
        async def cancel_handler(params: CancelTaskParams):
            task_events.append(("cancelled", params.task_id))

        runner = test_server_runner(agentic_base_acp, free_port)
        await runner.start()

        async with httpx.AsyncClient() as client:
            # Create task
            create_request = {
                "jsonrpc": "2.0",
                "method": "task/create",
                "params": {
                    "task": {
                        "id": "lifecycle-task",
                        "agent_id": "lifecycle-agent",
                        "status": "RUNNING",
                    }
                },
                "id": "create-1",
            }

            response = await client.post(f"http://127.0.0.1:{free_port}/api", json=create_request)
            assert response.status_code == 200

            # Send message
            message_request = {
                "jsonrpc": "2.0",
                "method": "event/send",
                "params": {
                    "task": {
                        "id": "lifecycle-task",
                        "agent_id": "lifecycle-agent",
                        "status": "RUNNING",
                    },
                    "message": {
                        "type": "text",
                        "author": "user",
                        "content": "Lifecycle test message",
                    },
                },
                "id": "message-1",
            }

            response = await client.post(f"http://127.0.0.1:{free_port}/api", json=message_request)
            assert response.status_code == 200

            # Cancel task
            cancel_request = {
                "jsonrpc": "2.0",
                "method": "task/cancel",
                "params": {"task_id": "lifecycle-task"},
                "id": "cancel-1",
            }

            response = await client.post(f"http://127.0.0.1:{free_port}/api", json=cancel_request)
            assert response.status_code == 200

        # Give background tasks time to process
        await asyncio.sleep(0.2)

        # Verify task lifecycle events
        assert len(task_events) == 3
        assert task_events[0] == ("created", "lifecycle-task")
        assert task_events[1] == ("message", "lifecycle-task")
        assert task_events[2] == ("cancelled", "lifecycle-task")

        await runner.stop()


class TestErrorRecovery:
    """Test error handling and recovery scenarios"""

    @pytest.mark.asyncio()
    async def test_server_resilience_to_handler_failures(
        self, sync_acp, free_port, test_server_runner
    ):
        """Test server continues working after handler failures"""
        failure_count = 0
        success_count = 0

        @sync_acp.on_task_event_send
        async def unreliable_handler(params: SendEventParams):
            nonlocal failure_count, success_count
            if "fail" in params.message.content:
                failure_count += 1
                raise RuntimeError("Simulated handler failure")
            else:
                success_count += 1
                return {"success": True}

        runner = test_server_runner(sync_acp, free_port)
        await runner.start()

        async with httpx.AsyncClient() as client:
            # Send failing request
            fail_request = {
                "jsonrpc": "2.0",
                "method": "event/send",
                "params": {
                    "task": {"id": "fail-task", "agent_id": "test-agent", "status": "RUNNING"},
                    "message": {"type": "text", "author": "user", "content": "This should fail"},
                },
                "id": "fail-1",
            }

            response = await client.post(f"http://127.0.0.1:{free_port}/api", json=fail_request)
            assert response.status_code == 200  # Server should still respond

            # Send successful request after failure
            success_request = {
                "jsonrpc": "2.0",
                "method": "event/send",
                "params": {
                    "task": {"id": "success-task", "agent_id": "test-agent", "status": "RUNNING"},
                    "message": {"type": "text", "author": "user", "content": "This should succeed"},
                },
                "id": "success-1",
            }

            response = await client.post(f"http://127.0.0.1:{free_port}/api", json=success_request)
            assert response.status_code == 200

            # Verify server is still healthy
            health_response = await client.get(f"http://127.0.0.1:{free_port}/healthz")
            assert health_response.status_code == 200

        # Give background tasks time to process
        await asyncio.sleep(0.2)

        assert failure_count == 1
        assert success_count == 1

        await runner.stop()

    @pytest.mark.asyncio()
    async def test_concurrent_request_handling(self, sync_acp, free_port, test_server_runner):
        """Test handling multiple concurrent requests"""
        processed_requests = []

        @sync_acp.on_task_event_send
        async def concurrent_handler(params: SendEventParams):
            # Simulate some processing time
            await asyncio.sleep(0.05)
            processed_requests.append(params.task.id)
            return {"processed": params.task.id}

        runner = test_server_runner(sync_acp, free_port)
        await runner.start()

        # Send multiple concurrent requests
        async def send_request(client, task_id):
            request_data = {
                "jsonrpc": "2.0",
                "method": "event/send",
                "params": {
                    "task": {"id": task_id, "agent_id": "concurrent-agent", "status": "RUNNING"},
                    "message": {
                        "type": "text",
                        "author": "user",
                        "content": f"Concurrent message for {task_id}",
                    },
                },
                "id": f"concurrent-{task_id}",
            }

            return await client.post(f"http://127.0.0.1:{free_port}/api", json=request_data)

        async with httpx.AsyncClient() as client:
            # Send 5 concurrent requests
            tasks = [send_request(client, f"task-{i}") for i in range(5)]
            responses = await asyncio.gather(*tasks)

            # All should return immediate acknowledgment
            for response in responses:
                assert response.status_code == 200
                data = response.json()
                assert data["result"]["status"] == "processing"

        # Give background tasks time to complete
        await asyncio.sleep(0.3)

        # All requests should have been processed
        assert len(processed_requests) == 5
        assert set(processed_requests) == {f"task-{i}" for i in range(5)}

        await runner.stop()


class TestSpecialCases:
    """Test edge cases and special scenarios"""

    @pytest.mark.asyncio()
    async def test_notification_vs_request_behavior(self, sync_acp, free_port, test_server_runner):
        """Test difference between notifications (no ID) and requests (with ID)"""
        notifications_received = 0
        requests_received = 0

        @sync_acp.on_task_event_send
        async def tracking_handler(params: SendEventParams):
            nonlocal notifications_received, requests_received
            if "notification" in params.message.content:
                notifications_received += 1
            else:
                requests_received += 1
            return {"handled": True}

        runner = test_server_runner(sync_acp, free_port)
        await runner.start()

        async with httpx.AsyncClient() as client:
            # Send notification (no ID)
            notification_data = {
                "jsonrpc": "2.0",
                "method": "event/send",
                "params": {
                    "task": {
                        "id": "notification-task",
                        "agent_id": "test-agent",
                        "status": "RUNNING",
                    },
                    "message": {
                        "type": "text",
                        "author": "user",
                        "content": "This is a notification",
                    },
                },
                # Note: no "id" field
            }

            notification_response = await client.post(
                f"http://127.0.0.1:{free_port}/api", json=notification_data
            )
            assert notification_response.status_code == 200
            notification_result = notification_response.json()
            assert notification_result["id"] is None

            # Send regular request (with ID)
            request_data = {
                "jsonrpc": "2.0",
                "method": "event/send",
                "params": {
                    "task": {"id": "request-task", "agent_id": "test-agent", "status": "RUNNING"},
                    "message": {"type": "text", "author": "user", "content": "This is a request"},
                },
                "id": "request-1",
            }

            request_response = await client.post(
                f"http://127.0.0.1:{free_port}/api", json=request_data
            )
            assert request_response.status_code == 200
            request_result = request_response.json()
            assert request_result["id"] == "request-1"
            assert request_result["result"]["status"] == "processing"

        # Give background tasks time to process
        await asyncio.sleep(0.1)

        assert notifications_received == 1
        assert requests_received == 1

        await runner.stop()

    @pytest.mark.asyncio()
    async def test_unicode_message_handling(self, sync_acp, free_port, test_server_runner):
        """Test handling of unicode characters in messages"""
        received_message = None

        @sync_acp.on_task_event_send
        async def unicode_handler(params: SendEventParams):
            nonlocal received_message
            received_message = params.message.content
            return {"unicode_handled": True}

        runner = test_server_runner(sync_acp, free_port)
        await runner.start()

        unicode_text = "Hello 世界 🌍 émojis 🚀 and special chars: \n\t\r"

        async with httpx.AsyncClient() as client:
            request_data = {
                "jsonrpc": "2.0",
                "method": "event/send",
                "params": {
                    "task": {
                        "id": "unicode-task",
                        "agent_id": "unicode-agent",
                        "status": "RUNNING",
                    },
                    "message": {"type": "text", "author": "user", "content": unicode_text},
                },
                "id": "unicode-test",
            }

            response = await client.post(f"http://127.0.0.1:{free_port}/api", json=request_data)

            assert response.status_code == 200

        # Give background task time to process
        await asyncio.sleep(0.1)

        assert received_message == unicode_text

        await runner.stop()


class TestImplementationIsolation:
    """Test that different implementations don't interfere with each other"""

    @pytest.mark.asyncio()
    async def test_handler_isolation_between_implementations(self):
        """Test handlers registered on one implementation don't affect others"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            sync_acp = SyncACP.create()
            agentic_acp = AgenticBaseACP.create()

            sync_handled = False
            agentic_handled = False

            @sync_acp.on_task_event_send
            async def sync_handler(params: SendEventParams):
                nonlocal sync_handled
                sync_handled = True
                return {"sync": True}

            @agentic_acp.on_task_event_send
            async def agentic_handler(params: SendEventParams):
                nonlocal agentic_handled
                agentic_handled = True
                return {"agentic": True}

            # Create test parameters
            message_params = SendEventParams(
                task={"id": "isolation-test-task", "agent_id": "test-agent", "status": "RUNNING"},
                message={"type": "text", "author": "user", "content": "Isolation test"},
            )

            # Execute sync handler
            sync_result = await sync_acp._handlers[RPCMethod.EVENT_SEND](message_params)
            assert sync_handled is True
            assert agentic_handled is False
            assert sync_result == {"sync": True}

            # Reset and execute agentic handler
            sync_handled = False
            agentic_result = await agentic_acp._handlers[RPCMethod.EVENT_SEND](message_params)
            assert sync_handled is False
            assert agentic_handled is True
            assert agentic_result == {"agentic": True}
