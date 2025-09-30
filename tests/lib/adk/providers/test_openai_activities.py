from unittest.mock import Mock, patch

import pytest
from agents import RunResult, RunResultStreaming
from temporalio.testing import ActivityEnvironment
from openai.types.responses import ResponseCodeInterpreterToolCall


class TestOpenAIActivities:
    @pytest.fixture
    def sample_run_result(self):
        """Create a sample RunResult for mocking."""
        mock_result = Mock(spec=RunResult)
        mock_result.final_output = "Hello! How can I help you today?"
        mock_result.to_input_list.return_value = [
            {"role": "user", "content": "Hello, world!"},
            {"role": "assistant", "content": "Hello! How can I help you today?"},
        ]
        # Add new_items attribute that the OpenAIService expects
        mock_result.new_items = []
        return mock_result

    @pytest.mark.parametrize(
        "max_turns,should_be_passed",
        [
            (None, False),
            (7, True),  # Test with non-default value (default is 10)
        ],
    )
    @patch("agents.Runner.run")
    async def test_run_agent(self, mock_runner_run, max_turns, should_be_passed, sample_run_result):
        """Comprehensive test for run_agent covering all major scenarios."""
        from agentex.lib.core.temporal.activities.adk.providers.openai_activities import RunAgentParams

        # Arrange
        mock_runner_run.return_value = sample_run_result
        mock_tracer = self._create_mock_tracer()
        _, openai_activities, env = self._create_test_setup(mock_tracer)

        # Create params with or without max_turns
        params = RunAgentParams(
            input_list=[{"role": "user", "content": "Hello, world!"}],
            mcp_server_params=[],
            agent_name="test_agent",
            agent_instructions="You are a helpful assistant",
            max_turns=max_turns,
            trace_id="test-trace-id",
            parent_span_id="test-span-id",
        )

        # Act
        result = await env.run(openai_activities.run_agent, params)

        # Assert - Result structure
        self._assert_result_structure(result)

        # Assert - Runner call
        mock_runner_run.assert_called_once()
        call_args = mock_runner_run.call_args

        # Assert - Runner signature validation
        self._assert_runner_call_signature(call_args)

        # Assert - Input parameter matches
        assert call_args.kwargs["input"] == params.input_list

        # Assert - Starting agent parameters
        starting_agent = call_args.kwargs["starting_agent"]
        self._assert_starting_agent_params(starting_agent, params)

        # Assert - Max turns parameter handling
        if should_be_passed:
            assert "max_turns" in call_args.kwargs, f"max_turns should be passed when set to {max_turns}"
            assert call_args.kwargs["max_turns"] == max_turns, f"max_turns value should be {max_turns}"
        else:
            assert "max_turns" not in call_args.kwargs, "max_turns should not be passed when None"

    @pytest.mark.parametrize(
        "previous_response_id,should_be_passed",
        [
            (None, False),
            ("response_123", True),
        ],
    )
    @patch("agents.Runner.run")
    async def test_run_agent_previous_response_id(
        self, mock_runner_run, previous_response_id, should_be_passed, sample_run_result
    ):
        """Test run_agent with previous_response_id parameter."""
        from agentex.lib.core.temporal.activities.adk.providers.openai_activities import RunAgentParams

        # Arrange
        mock_runner_run.return_value = sample_run_result
        mock_tracer = self._create_mock_tracer()
        _, openai_activities, env = self._create_test_setup(mock_tracer)

        # Create params with or without previous_response_id
        params = RunAgentParams(
            input_list=[{"role": "user", "content": "Hello, world!"}],
            mcp_server_params=[],
            agent_name="test_agent",
            agent_instructions="You are a helpful assistant",
            previous_response_id=previous_response_id,
            trace_id="test-trace-id",
            parent_span_id="test-span-id",
        )

        # Act
        result = await env.run(openai_activities.run_agent, params)

        # Assert - Result structure
        self._assert_result_structure(result)

        # Assert - Runner call
        mock_runner_run.assert_called_once()
        call_args = mock_runner_run.call_args

        # Assert - Runner signature validation
        self._assert_runner_call_signature(call_args)

        # Assert - Previous response ID parameter handling
        if should_be_passed:
            assert "previous_response_id" in call_args.kwargs, (
                f"previous_response_id should be passed when set to {previous_response_id}"
            )
            assert call_args.kwargs["previous_response_id"] == previous_response_id, (
                f"previous_response_id value should be {previous_response_id}"
            )
        else:
            assert "previous_response_id" not in call_args.kwargs, "previous_response_id should not be passed when None"

    @pytest.mark.parametrize(
        "tools_case",
        [
            "no_tools",
            "function_tool",
            "web_search_tool",
            "file_search_tool",
            "computer_tool",
            "code_interpreter_tool",
            "image_generation_tool",
            "local_shell_tool",
            "mixed_tools",
        ],
    )
    @patch("agents.Runner.run")
    async def test_run_agent_tools_conversion(self, mock_runner_run, tools_case, sample_run_result):
        """Test that tools are properly converted from Temporal to OpenAI agents format."""
        from agentex.lib.core.temporal.activities.adk.providers.openai_activities import (
            RunAgentParams,
        )

        # Arrange
        mock_runner_run.return_value = sample_run_result
        mock_tracer = self._create_mock_tracer()
        _, openai_activities, env = self._create_test_setup(mock_tracer)

        # Create different tool configurations based on test case
        tools = self._create_tools_for_case(tools_case)

        params = RunAgentParams(
            input_list=[{"role": "user", "content": "Hello, world!"}],
            mcp_server_params=[],
            agent_name="test_agent",
            agent_instructions="You are a helpful assistant",
            tools=tools,
            trace_id="test-trace-id",
            parent_span_id="test-span-id",
        )

        # Act
        result = await env.run(openai_activities.run_agent, params)

        # Assert - Result structure
        self._assert_result_structure(result)

        # Assert - Runner call
        mock_runner_run.assert_called_once()
        call_args = mock_runner_run.call_args

        # Assert - Runner signature validation
        self._assert_runner_call_signature(call_args)

        # Assert - Agent was created and tools were converted properly
        starting_agent = call_args.kwargs["starting_agent"]
        self._assert_tools_conversion(starting_agent, tools_case, tools)

    @patch("agents.Runner.run")
    async def test_run_agent_auto_send_with_tool_responses(self, mock_runner_run):
        """Test run_agent_auto_send with code interpreter tool responses."""
        from agentex.lib.core.temporal.activities.adk.providers.openai_activities import (
            CodeInterpreterTool,
            RunAgentAutoSendParams,
        )

        # Arrange - Setup test environment
        mock_tracer = self._create_mock_tracer()
        openai_service, openai_activities, env = self._create_test_setup(mock_tracer)
        mock_streaming_context = self._setup_streaming_service_mocks(openai_service)

        # Create tool call and response mocks using helpers
        code_interpreter_call = self._create_code_interpreter_tool_call_mock()
        mock_tool_call_item = self._create_tool_call_item_mock(code_interpreter_call)
        mock_tool_output_item = self._create_tool_output_item_mock()

        # Create a mock result with tool calls that will be processed
        mock_result_with_tools = Mock(spec=RunResult)
        mock_result_with_tools.final_output = "Code executed successfully"
        mock_result_with_tools.to_input_list.return_value = [
            {"role": "user", "content": "Run some Python code"},
            {"role": "assistant", "content": "Code executed successfully"},
        ]
        mock_result_with_tools.new_items = [mock_tool_call_item, mock_tool_output_item]
        mock_runner_run.return_value = mock_result_with_tools

        # Create test parameters
        params = RunAgentAutoSendParams(
            input_list=[{"role": "user", "content": "Run some Python code"}],
            mcp_server_params=[],
            agent_name="test_agent",
            agent_instructions=("You are a helpful assistant with code interpreter"),
            tools=[CodeInterpreterTool(tool_config={"type": "code_interpreter"})],
            trace_id="test-trace-id",
            parent_span_id="test-span-id",
            task_id="test-task-id",
        )

        result = await env.run(openai_activities.run_agent_auto_send, params)

        assert result.final_output == "Code executed successfully"

        # Verify runner.run was called with expected signature
        mock_runner_run.assert_called_once()
        call_args = mock_runner_run.call_args
        self._assert_runner_call_signature(call_args)

        # Verify starting agent parameters
        starting_agent = call_args.kwargs["starting_agent"]
        # Create a mock object with the expected attributes
        expected_params = Mock()
        expected_params.agent_name = "test_agent"
        expected_params.agent_instructions = "You are a helpful assistant with code interpreter"
        expected_params.tools = [CodeInterpreterTool(tool_config={"type": "code_interpreter"})]
        self._assert_starting_agent_params(starting_agent, expected_params)

        # Verify streaming context received tool request and response updates
        # Should have been called twice - once for tool request, once for response
        assert mock_streaming_context.stream_update.call_count == 2

        # First call should be tool request
        first_call = mock_streaming_context.stream_update.call_args_list[0]
        first_update = first_call[1]["update"]  # keyword argument
        assert hasattr(first_update, "content")
        assert first_update.content.name == "code_interpreter"
        assert first_update.content.tool_call_id == "code_interpreter_call_123"

        # Second call should be tool response
        second_call = mock_streaming_context.stream_update.call_args_list[1]
        second_update = second_call[1]["update"]  # keyword argument
        assert hasattr(second_update, "content")
        assert second_update.content.name == "code_interpreter_call"
        assert second_update.content.tool_call_id == "code_interpreter_call_123"

    @patch("agents.Runner.run_streamed")
    async def test_run_agent_streamed_auto_send(self, mock_runner_run_streamed):
        """Test run_agent_streamed_auto_send with streaming and tool responses."""
        from agentex.lib.core.temporal.activities.adk.providers.openai_activities import (
            CodeInterpreterTool,
            RunAgentStreamedAutoSendParams,
        )

        # Create streaming result mock using helper
        mock_streaming_result = self._create_streaming_result_mock()

        # Create mock streaming events
        async def mock_stream_events():
            # Tool call event
            tool_call_event = Mock()
            tool_call_event.type = "run_item_stream_event"
            tool_call_item = Mock()
            tool_call_item.type = "tool_call_item"
            tool_call_item.raw_item = self._create_code_interpreter_tool_call_mock()
            tool_call_event.item = tool_call_item
            yield tool_call_event

            # Tool response event
            tool_response_event = Mock()
            tool_response_event.type = "run_item_stream_event"
            tool_response_item = Mock()
            tool_response_item.type = "tool_call_output_item"
            tool_response_item.raw_item = {"call_id": "code_interpreter_call_123", "output": "Hello from streaming"}
            tool_response_event.item = tool_response_item
            yield tool_response_event

        mock_streaming_result.stream_events = mock_stream_events
        mock_runner_run_streamed.return_value = mock_streaming_result

        # Setup test environment
        mock_tracer = self._create_mock_tracer()
        openai_service, openai_activities, env = self._create_test_setup(mock_tracer)
        mock_streaming_context = self._setup_streaming_service_mocks(openai_service)

        # Create test parameters
        params = RunAgentStreamedAutoSendParams(
            input_list=[{"role": "user", "content": "Run some Python code"}],
            mcp_server_params=[],
            agent_name="test_agent",
            agent_instructions=("You are a helpful assistant with code interpreter"),
            tools=[CodeInterpreterTool(tool_config={"type": "code_interpreter"})],
            trace_id="test-trace-id",
            parent_span_id="test-span-id",
            task_id="test-task-id",
        )

        # Act
        result = await env.run(openai_activities.run_agent_streamed_auto_send, params)

        # Assert - Result structure (expecting SerializableRunResultStreaming from activity)
        from agentex.lib.types.agent_results import SerializableRunResultStreaming

        assert isinstance(result, SerializableRunResultStreaming)
        assert result.final_output == "Code executed successfully"

        # Verify runner.run_streamed was called with expected signature
        mock_runner_run_streamed.assert_called_once()
        call_args = mock_runner_run_streamed.call_args
        self._assert_runner_call_signature_streamed(call_args)

        # Verify starting agent parameters
        starting_agent = call_args.kwargs["starting_agent"]
        # Create a mock object with the expected attributes
        expected_params = Mock()
        expected_params.agent_name = "test_agent"
        expected_params.agent_instructions = "You are a helpful assistant with code interpreter"
        expected_params.tools = [CodeInterpreterTool(tool_config={"type": "code_interpreter"})]
        self._assert_starting_agent_params(starting_agent, expected_params)

        # Verify streaming context received tool request and response updates
        # Should have been called twice - once for tool request, once for response
        assert mock_streaming_context.stream_update.call_count == 2

        # First call should be tool request
        first_call = mock_streaming_context.stream_update.call_args_list[0]
        first_update = first_call[1]["update"]  # keyword argument
        assert hasattr(first_update, "content")
        assert first_update.content.name == "code_interpreter"
        assert first_update.content.tool_call_id == "code_interpreter_call_123"

        # Second call should be tool response
        second_call = mock_streaming_context.stream_update.call_args_list[1]
        second_update = second_call[1]["update"]  # keyword argument
        assert hasattr(second_update, "content")
        assert second_update.content.name == "code_interpreter_call"
        assert second_update.content.tool_call_id == "code_interpreter_call_123"

    def _create_mock_tracer(self):
        """Helper method to create a properly mocked tracer with async context manager support."""
        mock_tracer = Mock()
        mock_trace = Mock()
        mock_span = Mock()

        # Setup the span context manager
        async def mock_span_aenter(_):
            return mock_span

        async def mock_span_aexit(_, _exc_type, _exc_val, _exc_tb):
            return None

        mock_span.__aenter__ = mock_span_aenter
        mock_span.__aexit__ = mock_span_aexit
        mock_trace.span.return_value = mock_span
        mock_tracer.trace.return_value = mock_trace

        return mock_tracer

    def _create_test_setup(self, mock_tracer):
        """Helper method to create OpenAIService and OpenAIActivities instances."""
        # Import here to avoid circular imports
        from agentex.lib.core.services.adk.providers.openai import OpenAIService
        from agentex.lib.core.temporal.activities.adk.providers.openai_activities import OpenAIActivities

        openai_service = OpenAIService(tracer=mock_tracer)
        openai_activities = OpenAIActivities(openai_service)
        env = ActivityEnvironment()

        return openai_service, openai_activities, env

    def _assert_runner_call_signature(self, call_args):
        """Helper method to validate Runner.run call signature."""
        actual_kwargs = set(call_args.kwargs.keys())

        # Check that we only pass valid Runner.run parameters
        valid_params = {
            "starting_agent",
            "input",
            "context",
            "max_turns",
            "hooks",
            "run_config",
            "previous_response_id",
            "session",
        }
        invalid_kwargs = actual_kwargs - valid_params
        assert not invalid_kwargs, f"Invalid arguments passed to Runner.run: {invalid_kwargs}"

        # Verify required arguments are present
        assert "starting_agent" in call_args.kwargs, "starting_agent is required for Runner.run"
        assert "input" in call_args.kwargs, "input is required for Runner.run"

        # Verify starting_agent is not None (actual agent object created)
        assert call_args.kwargs["starting_agent"] is not None, "starting_agent should not be None"

    def _assert_runner_call_signature_streamed(self, call_args):
        """Helper method to validate Runner.run_streamed call signature."""
        actual_kwargs = set(call_args.kwargs.keys())

        # Check that we only pass valid Runner.run_streamed parameters
        valid_params = {
            "starting_agent",
            "input",
            "context",
            "max_turns",
            "hooks",
            "run_config",
            "previous_response_id",
            "session",
        }
        invalid_kwargs = actual_kwargs - valid_params
        assert not invalid_kwargs, f"Invalid arguments passed to Runner.run_streamed: {invalid_kwargs}"

        # Verify required arguments are present
        assert "starting_agent" in call_args.kwargs, "starting_agent is required for Runner.run_streamed"
        assert "input" in call_args.kwargs, "input is required for Runner.run_streamed"

        # Verify starting_agent is not None (actual agent object created)
        assert call_args.kwargs["starting_agent"] is not None, "starting_agent should not be None"

    def _assert_starting_agent_params(self, starting_agent, expected_params):
        """Helper method to validate starting_agent parameters match expected values."""
        # Verify agent name and instructions match
        assert starting_agent.name == expected_params.agent_name, f"Agent name should be {expected_params.agent_name}"
        assert starting_agent.instructions == expected_params.agent_instructions, f"Agent instructions should match"

        # Note: Other agent parameters like tools, guardrails would be tested here
        # but they require more complex inspection of the agent object

    def _assert_result_structure(self, result, expected_output="Hello! How can I help you today?"):
        """Helper method to validate the result structure."""
        from agentex.lib.types.agent_results import SerializableRunResult

        assert isinstance(result, SerializableRunResult)
        assert result.final_output == expected_output
        assert len(result.final_input_list) == 2
        assert result.final_input_list[0]["role"] == "user"
        assert result.final_input_list[1]["role"] == "assistant"

    def _create_tools_for_case(self, tools_case):
        """Helper method to create tools based on test case."""
        from agentex.lib.core.temporal.activities.adk.providers.openai_activities import (
            ComputerTool,
            FunctionTool,
            WebSearchTool,
            FileSearchTool,
            LocalShellTool,
            CodeInterpreterTool,
            ImageGenerationTool,
        )

        def sample_tool_function(_context, args):
            return f"Tool called with {args}"

        def sample_computer():
            return Mock()  # Mock computer object

        def sample_safety_check(_data):
            return True

        def sample_executor():
            return Mock()  # Mock executor

        if tools_case == "no_tools":
            return None
        elif tools_case == "function_tool":
            return [
                FunctionTool(
                    name="test_function",
                    description="A test function tool",
                    params_json_schema={"type": "object", "properties": {}},
                    on_invoke_tool=sample_tool_function,
                )
            ]
        elif tools_case == "web_search_tool":
            return [WebSearchTool()]
        elif tools_case == "file_search_tool":
            return [
                FileSearchTool(vector_store_ids=["store1", "store2"], max_num_results=10, include_search_results=True)
            ]
        elif tools_case == "computer_tool":
            return [ComputerTool(computer=sample_computer(), on_safety_check=sample_safety_check)]
        elif tools_case == "code_interpreter_tool":
            return [
                CodeInterpreterTool(
                    tool_config={"type": "code_interpreter", "container": {"type": "static", "image": "python:3.11"}}
                )
            ]
        elif tools_case == "image_generation_tool":
            return [
                ImageGenerationTool(
                    tool_config={
                        "type": "image_generation",
                        "quality": "high",
                        "size": "1024x1024",
                        "output_format": "png",
                    }
                )
            ]
        elif tools_case == "local_shell_tool":
            return [LocalShellTool(executor=sample_executor())]
        elif tools_case == "mixed_tools":
            return [
                FunctionTool(
                    name="calculator",
                    description="A calculator tool",
                    params_json_schema={"type": "object", "properties": {"expression": {"type": "string"}}},
                    on_invoke_tool=sample_tool_function,
                ),
                WebSearchTool(),
                FileSearchTool(vector_store_ids=["store1"], max_num_results=5),
            ]
        else:
            raise ValueError(f"Unknown tools_case: {tools_case}")

    def _assert_tools_conversion(self, starting_agent, tools_case, _original_tools):
        """Helper method to validate that tools were properly converted."""
        from agents.tool import (
            ComputerTool as OAIComputerTool,
            FunctionTool as OAIFunctionTool,
            WebSearchTool as OAIWebSearchTool,
            FileSearchTool as OAIFileSearchTool,
            LocalShellTool as OAILocalShellTool,
            CodeInterpreterTool as OAICodeInterpreterTool,
            ImageGenerationTool as OAIImageGenerationTool,
        )

        if tools_case == "no_tools":
            # When no tools are provided, the agent should have an empty tools list
            assert starting_agent.tools == [], "Agent should have empty tools list when no tools provided"

        elif tools_case == "function_tool":
            assert len(starting_agent.tools) == 1, "Agent should have 1 tool"
            agent_tool = starting_agent.tools[0]
            assert isinstance(agent_tool, OAIFunctionTool), "Tool should be converted to OAIFunctionTool"
            assert agent_tool.name == "test_function", "Tool name should be preserved"
            assert agent_tool.description == "A test function tool", "Tool description should be preserved"
            # Check that the schema contains our expected fields (may have additional fields)
            assert "type" in agent_tool.params_json_schema, "Tool schema should have type field"
            assert agent_tool.params_json_schema["type"] == "object", "Tool schema type should be object"
            assert "properties" in agent_tool.params_json_schema, "Tool schema should have properties field"
            assert callable(agent_tool.on_invoke_tool), "Tool function should be callable"

        elif tools_case == "web_search_tool":
            assert len(starting_agent.tools) == 1, "Agent should have 1 tool"
            agent_tool = starting_agent.tools[0]
            assert isinstance(agent_tool, OAIWebSearchTool), "Tool should be converted to OAIWebSearchTool"

        elif tools_case == "file_search_tool":
            assert len(starting_agent.tools) == 1, "Agent should have 1 tool"
            agent_tool = starting_agent.tools[0]
            assert isinstance(agent_tool, OAIFileSearchTool), "Tool should be converted to OAIFileSearchTool"
            assert agent_tool.vector_store_ids == ["store1", "store2"], "Vector store IDs should be preserved"
            assert agent_tool.max_num_results == 10, "Max results should be preserved"
            assert agent_tool.include_search_results, "Include search results flag should be preserved"

        elif tools_case == "computer_tool":
            assert len(starting_agent.tools) == 1, "Agent should have 1 tool"
            agent_tool = starting_agent.tools[0]
            assert isinstance(agent_tool, OAIComputerTool), "Tool should be converted to OAIComputerTool"
            assert agent_tool.computer is not None, "Computer object should be present"
            assert agent_tool.on_safety_check is not None, "Safety check function should be present"

        elif tools_case == "code_interpreter_tool":
            assert len(starting_agent.tools) == 1, "Agent should have 1 tool"
            agent_tool = starting_agent.tools[0]
            assert isinstance(agent_tool, OAICodeInterpreterTool), "Tool should be converted to OAICodeInterpreterTool"

        elif tools_case == "image_generation_tool":
            assert len(starting_agent.tools) == 1, "Agent should have 1 tool"
            agent_tool = starting_agent.tools[0]
            assert isinstance(agent_tool, OAIImageGenerationTool), "Tool should be converted to OAIImageGenerationTool"

        elif tools_case == "local_shell_tool":
            assert len(starting_agent.tools) == 1, "Agent should have 1 tool"
            agent_tool = starting_agent.tools[0]
            assert isinstance(agent_tool, OAILocalShellTool), "Tool should be converted to OAILocalShellTool"
            assert agent_tool.executor is not None, "Executor should be present"

        elif tools_case == "mixed_tools":
            assert len(starting_agent.tools) == 3, "Agent should have 3 tools"

            # Check first tool (FunctionTool)
            function_tool = starting_agent.tools[0]
            assert isinstance(function_tool, OAIFunctionTool), "First tool should be OAIFunctionTool"
            assert function_tool.name == "calculator", "Function tool name should be preserved"

            # Check second tool (WebSearchTool)
            web_tool = starting_agent.tools[1]
            assert isinstance(web_tool, OAIWebSearchTool), "Second tool should be OAIWebSearchTool"

            # Check third tool (FileSearchTool)
            file_tool = starting_agent.tools[2]
            assert isinstance(file_tool, OAIFileSearchTool), "Third tool should be OAIFileSearchTool"

        else:
            raise ValueError(f"Unknown tools_case: {tools_case}")

    def _setup_streaming_service_mocks(self, openai_service):
        """Helper method to setup streaming service mocks for run_agent_auto_send."""
        from unittest.mock import AsyncMock

        # Mock the streaming service and agentex client
        mock_streaming_service = AsyncMock()
        mock_agentex_client = AsyncMock()

        # Mock streaming context manager
        mock_streaming_context = AsyncMock()

        # Create a proper TaskMessage mock that passes validation
        from agentex.types.task_message import TaskMessage

        mock_task_message = Mock(spec=TaskMessage)
        mock_task_message.id = "test-task-message-id"
        mock_task_message.task_id = "test-task-id"
        mock_task_message.content = {"type": "text", "content": "test"}

        mock_streaming_context.task_message = mock_task_message
        mock_streaming_context.stream_update = AsyncMock()

        # Create a proper async context manager mock
        from contextlib import asynccontextmanager
        from unittest.mock import AsyncMock

        @asynccontextmanager
        async def mock_streaming_context_manager(*_args, **_kwargs):
            yield mock_streaming_context

        mock_streaming_service.streaming_task_message_context = mock_streaming_context_manager

        openai_service.streaming_service = mock_streaming_service
        openai_service.agentex_client = mock_agentex_client

        return mock_streaming_context

    def _create_code_interpreter_tool_call_mock(self, call_id="code_interpreter_call_123"):
        """Helper to create ResponseCodeInterpreterToolCall mock objects."""
        return ResponseCodeInterpreterToolCall(
            id=call_id,
            type="code_interpreter_call",
            status="completed",
            code="print('Hello from code interpreter')",
            container_id="container_123",
            outputs=[],
        )

    def _create_tool_call_item_mock(self, tool_call):
        """Helper to create tool call item mock."""
        mock_tool_call_item = Mock()
        mock_tool_call_item.type = "tool_call_item"
        mock_tool_call_item.raw_item = tool_call
        return mock_tool_call_item

    def _create_tool_output_item_mock(self, call_id="code_interpreter_call_123", output="Hello from code interpreter"):
        """Helper to create tool output item mock."""
        mock_tool_output_item = Mock()
        mock_tool_output_item.type = "tool_call_output_item"
        mock_tool_output_item.raw_item = {"call_id": call_id, "output": output}
        return mock_tool_output_item

    def _create_streaming_result_mock(self, final_output="Code executed successfully"):
        """Helper to create streaming result mock with common setup."""
        mock_streaming_result = Mock(spec=RunResultStreaming)
        mock_streaming_result.final_output = final_output
        mock_streaming_result.new_items = []
        mock_streaming_result.final_input_list = [
            {"role": "user", "content": "Run some Python code"},
            {"role": "assistant", "content": final_output},
        ]
        mock_streaming_result.to_input_list.return_value = [
            {"role": "user", "content": "Run some Python code"},
            {"role": "assistant", "content": final_output},
        ]
        return mock_streaming_result

    def _create_common_agent_params(self, **overrides):
        """Helper to create common agent parameters with defaults."""
        defaults = {
            "input_list": [{"role": "user", "content": "Run some Python code"}],
            "mcp_server_params": [],
            "agent_name": "test_agent",
            "agent_instructions": "You are a helpful assistant with code interpreter",
            "trace_id": "test-trace-id",
            "parent_span_id": "test-span-id",
            "task_id": "test-task-id",
        }
        defaults.update(overrides)
        return defaults
