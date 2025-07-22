import asyncio
import socket
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
import uvicorn

from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer
from agentex.lib.sdk.fastacp.impl.agentic_base_acp import AgenticBaseACP
from agentex.lib.sdk.fastacp.impl.sync_acp import SyncACP
from agentex.lib.sdk.fastacp.impl.temporal_acp import TemporalACP
from agentex.lib.types.acp import (
    CancelTaskParams,
    CreateTaskParams,
    SendMessageParams,
)
from agentex.lib.types.json_rpc import JSONRPCRequest
from agentex.types.agent import Agent
from agentex.types.task_message import TaskMessageContent
from agentex.types.task_message_content import TextContent
from agentex.types.task import Task

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


def find_free_port() -> int:
    """Find a free port for testing"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@pytest.fixture
def free_port() -> int:
    """Fixture that provides a free port for testing"""
    return find_free_port()


@pytest.fixture
def sample_task() -> Task:
    """Fixture that provides a sample Task object"""
    return Task(
        id="test-task-123", agent_id="test-agent-456", status=TaskStatus.RUNNING
    )


@pytest.fixture
def sample_message_content() -> TaskMessageContent:
    """Fixture that provides a sample TaskMessage object"""
    return TextContent(
        type="text",
        author="user",
        content="Hello, this is a test message",
    )


@pytest.fixture
def sample_send_message_params(
    sample_task: Task, sample_message_content: TaskMessageContent
) -> SendMessageParams:
    """Fixture that provides sample SendMessageParams"""
    return SendMessageParams(
        agent=Agent(
            id="test-agent-456",
            name="test-agent",
            description="test-agent",
            acp_type="sync",
        ),
        task=sample_task,
        content=sample_message_content,
        stream=False,
    )


@pytest.fixture
def sample_cancel_task_params() -> CancelTaskParams:
    """Fixture that provides sample CancelTaskParams"""
    return CancelTaskParams(
        agent=Agent(id="test-agent-456", name="test-agent", description="test-agent", acp_type="sync"),
        task=Task(id="test-task-123", agent_id="test-agent-456", status="running"),
    )


@pytest.fixture
def sample_create_task_params(sample_task: Task) -> CreateTaskParams:
    """Fixture that provides sample CreateTaskParams"""
    return CreateTaskParams(
        agent=Agent(id="test-agent-456", name="test-agent", description="test-agent", acp_type="sync"),
        task=sample_task,
        params={},
    )


class TestServerRunner:
    """Utility class for running test servers"""

    def __init__(self, app: BaseACPServer, port: int):
        self.app = app
        self.port = port
        self.server = None
        self.server_task = None

    async def start(self):
        """Start the server in a background task"""
        config = uvicorn.Config(
            app=self.app,
            host="127.0.0.1",
            port=self.port,
            log_level="error",  # Reduce noise in tests
        )
        self.server = uvicorn.Server(config)
        self.server_task = asyncio.create_task(self.server.serve())

        # Wait for server to be ready
        await self._wait_for_server()

    async def stop(self):
        """Stop the server"""
        if self.server:
            self.server.should_exit = True
        if self.server_task:
            try:
                await asyncio.wait_for(self.server_task, timeout=5.0)
            except TimeoutError:
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass

    async def _wait_for_server(self, timeout: float = 10.0):
        """Wait for server to be ready to accept connections"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"http://127.0.0.1:{self.port}/healthz")
                    if response.status_code == 200:
                        return
            except (httpx.ConnectError, httpx.ConnectTimeout):
                await asyncio.sleep(0.1)
        raise TimeoutError(f"Server did not start within {timeout} seconds")


@pytest_asyncio.fixture
async def test_server_runner():
    """Fixture that provides a TestServerRunner factory"""
    runners = []

    def create_runner(app: BaseACPServer, port: int) -> TestServerRunner:
        runner = TestServerRunner(app, port)
        runners.append(runner)
        return runner

    yield create_runner

    # Cleanup all runners
    for runner in runners:
        await runner.stop()


@pytest.fixture
def base_acp_server():
    """Fixture that provides a BaseACPServer instance for sync tests"""
    with patch.dict(
        "os.environ", {"AGENTEX_BASE_URL": ""}
    ):  # Disable agent registration
        server = BaseACPServer()
        return server


@pytest_asyncio.fixture
async def async_base_acp_server():
    """Fixture that provides a BaseACPServer instance for async tests"""
    with patch.dict(
        "os.environ", {"AGENTEX_BASE_URL": ""}
    ):  # Disable agent registration
        server = BaseACPServer.create()
        return server


@pytest.fixture
def sync_acp_server():
    """Fixture that provides a SyncACP instance for sync tests"""
    with patch.dict(
        "os.environ", {"AGENTEX_BASE_URL": ""}
    ):  # Disable agent registration
        server = SyncACP()
        return server


@pytest_asyncio.fixture
async def async_sync_acp_server():
    """Fixture that provides a SyncACP instance for async tests"""
    with patch.dict(
        "os.environ", {"AGENTEX_BASE_URL": ""}
    ):  # Disable agent registration
        server = await SyncACP.create()
        return server


@pytest.fixture
def agentic_base_acp_server():
    """Fixture that provides an AgenticBaseACP instance for sync tests"""
    with patch.dict(
        "os.environ", {"AGENTEX_BASE_URL": ""}
    ):  # Disable agent registration
        server = AgenticBaseACP()
        return server


@pytest_asyncio.fixture
async def async_agentic_base_acp_server():
    """Fixture that provides an AgenticBaseACP instance for async tests"""
    with patch.dict(
        "os.environ", {"AGENTEX_BASE_URL": ""}
    ):  # Disable agent registration
        server = await AgenticBaseACP.create()
        return server


@pytest_asyncio.fixture
async def mock_temporal_acp_server():
    """Fixture that provides a mocked TemporalACP instance"""
    with patch.dict(
        "os.environ", {"AGENTEX_BASE_URL": ""}
    ):  # Disable agent registration
        with patch(
            "agentex.sdk.fastacp.impl.temporal_acp.TemporalClient"
        ) as mock_temporal_client:
            with patch(
                "agentex.sdk.fastacp.impl.temporal_acp.AsyncAgentexClient"
            ) as mock_agentex_client:
                # Mock the temporal client creation
                mock_temporal_client.create.return_value = AsyncMock()
                mock_agentex_client.return_value = AsyncMock()

                server = await TemporalACP.create(temporal_address="localhost:7233")
                return server


class JSONRPCTestClient:
    """Test client for making JSON-RPC requests"""

    def __init__(self, base_url: str):
        self.base_url = base_url

    async def call_method(
        self, method: str, params: dict[str, Any], request_id: str | None = "test-1"
    ) -> dict[str, Any]:
        """Make a JSON-RPC method call"""
        request = JSONRPCRequest(method=method, params=params, id=request_id)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api",
                json=request.model_dump(),
                headers={"Content-Type": "application/json"},
            )
            return response.json()

    async def send_notification(
        self, method: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Send a JSON-RPC notification (no ID)"""
        return await self.call_method(method, params, request_id=None)

    async def health_check(self) -> dict[str, Any]:
        """Check server health"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/healthz")
            return response.json()


@pytest.fixture
def jsonrpc_client_factory():
    """Fixture that provides a JSONRPCTestClient factory"""

    def create_client(base_url: str) -> JSONRPCTestClient:
        return JSONRPCTestClient(base_url)

    return create_client


# Mock environment variables for testing
@pytest.fixture
def mock_env_vars():
    """Fixture that mocks environment variables"""
    env_vars = {
        "AGENTEX_BASE_URL": "",  # Disable agent registration by default
        "AGENT_NAME": "test-agent",
        "AGENT_DESCRIPTION": "Test agent description",
        "ACP_URL": "http://localhost",
        "ACP_PORT": "8000",
        "WORKFLOW_NAME": "test-workflow",
        "WORKFLOW_TASK_QUEUE": "test-queue",
    }

    with patch.dict("os.environ", env_vars):
        yield env_vars
