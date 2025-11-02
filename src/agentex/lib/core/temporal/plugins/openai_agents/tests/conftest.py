"""
Pytest configuration and fixtures for StreamingModel tests.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from agents import (
    Handoff,
    FunctionTool,
    ModelSettings,
)
from agents.tool import (
    ComputerTool,
    HostedMCPTool,
    WebSearchTool,
    FileSearchTool,
    LocalShellTool,
    CodeInterpreterTool,
    ImageGenerationTool,
)
from agents.model_settings import Reasoning  # type: ignore[attr-defined]
from openai.types.responses import (
    ResponseCompletedEvent,
    ResponseTextDeltaEvent,
    ResponseOutputItemAddedEvent,
    ResponseReasoningSummaryTextDeltaEvent,
)

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def mock_openai_client():
    """Mock AsyncOpenAI client"""
    client = MagicMock()
    client.responses = MagicMock()
    return client


@pytest.fixture
def sample_task_id():
    """Generate a sample task ID"""
    return f"task_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def mock_streaming_context():
    """Mock streaming context for testing"""
    context = AsyncMock()
    context.task_message = MagicMock()
    context.stream_update = AsyncMock()
    context.close = AsyncMock()
    context.__aenter__ = AsyncMock(return_value=context)
    context.__aexit__ = AsyncMock()
    return context


@pytest.fixture(autouse=True)
def mock_adk_streaming():
    """Mock the ADK streaming module"""
    with patch('agentex.lib.adk.streaming') as mock_streaming:
        mock_context = AsyncMock()
        mock_context.task_message = MagicMock()
        mock_context.stream_update = AsyncMock()
        mock_context.close = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_context)
        mock_context.__aexit__ = AsyncMock()

        mock_streaming.streaming_task_message_context.return_value = mock_context
        yield mock_streaming


@pytest.fixture
def sample_function_tool():
    """Sample FunctionTool for testing"""
    async def mock_tool_handler(_context, _args):
        return {"temperature": "72F", "condition": "sunny"}

    return FunctionTool(
        name="get_weather",
        description="Get the current weather",
        params_json_schema={
            "type": "object",
            "properties": {
                "location": {"type": "string"}
            }
        },
        on_invoke_tool=mock_tool_handler,
        strict_json_schema=False
    )


@pytest.fixture
def sample_web_search_tool():
    """Sample WebSearchTool for testing"""
    return WebSearchTool(
        user_location=None,
        search_context_size="medium"
    )


@pytest.fixture
def sample_file_search_tool():
    """Sample FileSearchTool for testing"""
    return FileSearchTool(
        vector_store_ids=["vs_123"],
        max_num_results=10,
        include_search_results=True
    )


@pytest.fixture
def sample_computer_tool():
    """Sample ComputerTool for testing"""
    computer = MagicMock()
    computer.environment = "desktop"
    computer.dimensions = [1920, 1080]
    return ComputerTool(computer=computer)


@pytest.fixture
def sample_hosted_mcp_tool():
    """Sample HostedMCPTool for testing"""
    tool = MagicMock(spec=HostedMCPTool)
    tool.tool_config = {
        "type": "mcp",
        "server_label": "test_server",
        "name": "test_tool"
    }
    return tool


@pytest.fixture
def sample_image_generation_tool():
    """Sample ImageGenerationTool for testing"""
    tool = MagicMock(spec=ImageGenerationTool)
    tool.tool_config = {
        "type": "image_generation",
        "model": "dall-e-3"
    }
    return tool


@pytest.fixture
def sample_code_interpreter_tool():
    """Sample CodeInterpreterTool for testing"""
    tool = MagicMock(spec=CodeInterpreterTool)
    tool.tool_config = {
        "type": "code_interpreter"
    }
    return tool


@pytest.fixture
def sample_local_shell_tool():
    """Sample LocalShellTool for testing"""
    from agents import LocalShellExecutor
    executor = MagicMock(spec=LocalShellExecutor)
    return LocalShellTool(executor=executor)


@pytest.fixture
def sample_handoff():
    """Sample Handoff for testing"""
    from agents import Agent

    async def mock_handoff_handler(_context, _args):
        # Return a mock agent
        return MagicMock(spec=Agent)

    return Handoff(
        agent_name="support_agent",
        tool_name="transfer_to_support",
        tool_description="Transfer to support agent",
        input_json_schema={"type": "object"},
        on_invoke_handoff=mock_handoff_handler
    )


@pytest.fixture
def basic_model_settings():
    """Basic ModelSettings for testing"""
    return ModelSettings(
        temperature=0.7,
        max_tokens=1000,
        top_p=0.9
    )


@pytest.fixture
def reasoning_model_settings():
    """ModelSettings with reasoning enabled"""
    return ModelSettings(
        reasoning=Reasoning(
            effort="medium",
            generate_summary="auto"
        )
    )


@pytest.fixture
def mock_response_stream():
    """Mock a response stream with basic events"""
    async def stream_generator():
        # Yield some basic events
        yield ResponseOutputItemAddedEvent(  # type: ignore[call-arg]
            type="response.output_item.added",
            output_index=0,
            item=MagicMock(type="message")
        )

        yield ResponseTextDeltaEvent(  # type: ignore[call-arg]
            type="response.text.delta",
            delta="Hello ",
            output_index=0
        )

        yield ResponseTextDeltaEvent(  # type: ignore[call-arg]
            type="response.text.delta",
            delta="world!",
            output_index=0
        )

        yield ResponseCompletedEvent(  # type: ignore[call-arg]
            type="response.completed",
            response=MagicMock(
                output=[],
                usage=MagicMock()
            )
        )

    return stream_generator()


@pytest.fixture
def mock_reasoning_stream():
    """Mock a response stream with reasoning events"""
    async def stream_generator():
        # Start reasoning
        yield ResponseOutputItemAddedEvent(  # type: ignore[call-arg]
            type="response.output_item.added",
            output_index=0,
            item=MagicMock(type="reasoning")
        )

        # Reasoning deltas
        yield ResponseReasoningSummaryTextDeltaEvent(  # type: ignore[call-arg]
            type="response.reasoning_summary_text.delta",
            delta="Let me think about this...",
            summary_index=0
        )

        # Complete
        yield ResponseCompletedEvent(  # type: ignore[call-arg]
            type="response.completed",
            response=MagicMock(
                output=[],
                usage=MagicMock()
            )
        )

    return stream_generator()


@pytest_asyncio.fixture(scope="function")
async def streaming_model():
    """Create a TemporalStreamingModel instance for testing"""
    from ..models.temporal_streaming_model import TemporalStreamingModel

    model = TemporalStreamingModel(model_name="gpt-4o")
    # Mock the OpenAI client with fresh mocks for each test
    model.client = AsyncMock()
    model.client.responses = AsyncMock()

    yield model

    # Cleanup after each test
    if hasattr(model.client, 'close'):
        await model.client.close()


# Mock environment variables for testing
@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mock environment variables"""
    env_vars = {
        "OPENAI_API_KEY": "test-key-123",
        "AGENT_NAME": "test-agent",
        "ACP_URL": "http://localhost:8000",
    }

    with patch.dict("os.environ", env_vars):
        yield env_vars