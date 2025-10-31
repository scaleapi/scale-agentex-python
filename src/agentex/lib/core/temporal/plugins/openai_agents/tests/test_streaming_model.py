"""
Comprehensive tests for StreamingModel with all configurations and tool types.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from agents import ModelSettings
from openai import NOT_GIVEN
from agents.model_settings import Reasoning, MCPToolChoice  # type: ignore[attr-defined]


class TestStreamingModelSettings:
    """Test that all ModelSettings parameters work with Responses API"""

    @pytest.mark.asyncio
    async def test_temperature_setting(self, streaming_model, _mock_adk_streaming, sample_task_id):
        """Test that temperature parameter is properly passed to Responses API"""
        streaming_model.client.responses.create = AsyncMock()

        # Mock the response stream
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        # Test with various temperature values
        for temp in [0.0, 0.7, 1.5, 2.0]:
            settings = ModelSettings(temperature=temp)

            await streaming_model.get_response(
                system_instructions="Test",
                input="Hello",
                model_settings=settings,
                tools=[],
                output_schema=None,
                handoffs=[],
                tracing=None,
                task_id=sample_task_id
            )

            # Verify temperature was passed correctly
            create_call = streaming_model.client.responses.create.call_args
            assert create_call.kwargs['temperature'] == temp

    @pytest.mark.asyncio
    async def test_top_p_setting(self, streaming_model, _mock_adk_streaming, sample_task_id):
        """Test that top_p parameter is properly passed to Responses API"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        # Test with various top_p values
        for top_p in [0.1, 0.5, 0.9, None]:
            settings = ModelSettings(top_p=top_p)

            await streaming_model.get_response(
                system_instructions="Test",
                input="Hello",
                model_settings=settings,
                tools=[],
                output_schema=None,
                handoffs=[],
                tracing=None,
                task_id=sample_task_id
            )

            create_call = streaming_model.client.responses.create.call_args
            expected = top_p if top_p is not None else NOT_GIVEN
            assert create_call.kwargs['top_p'] == expected

    @pytest.mark.asyncio
    async def test_max_tokens_setting(self, streaming_model, _mock_adk_streaming, sample_task_id):
        """Test that max_tokens is properly mapped to max_output_tokens"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        settings = ModelSettings(max_tokens=2000)

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=settings,
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        assert create_call.kwargs['max_output_tokens'] == 2000

    @pytest.mark.asyncio
    async def test_reasoning_effort_settings(self, streaming_model, _mock_adk_streaming, sample_task_id):
        """Test reasoning effort levels (low/medium/high)"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        for effort in ["low", "medium", "high"]:
            settings = ModelSettings(
                reasoning=Reasoning(effort=effort)
            )

            await streaming_model.get_response(
                system_instructions="Test",
                input="Hello",
                model_settings=settings,
                tools=[],
                output_schema=None,
                handoffs=[],
                tracing=None,
                task_id=sample_task_id
            )

            create_call = streaming_model.client.responses.create.call_args
            assert create_call.kwargs['reasoning'] == {"effort": effort}

    @pytest.mark.asyncio
    async def test_reasoning_summary_settings(self, streaming_model, _mock_adk_streaming, sample_task_id):
        """Test reasoning summary settings (auto/none)"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        for summary in ["auto", "concise", "detailed"]:
            settings = ModelSettings(
                reasoning=Reasoning(effort="medium", generate_summary=summary)
            )

            await streaming_model.get_response(
                system_instructions="Test",
                input="Hello",
                model_settings=settings,
                tools=[],
                output_schema=None,
                handoffs=[],
                tracing=None,
                task_id=sample_task_id
            )

            create_call = streaming_model.client.responses.create.call_args
            assert create_call.kwargs['reasoning'] == {"effort": "medium", "summary": summary}

    @pytest.mark.asyncio
    async def test_tool_choice_variations(self, streaming_model, _mock_adk_streaming, sample_task_id, sample_function_tool):
        """Test various tool_choice settings"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        # Test different tool_choice options
        test_cases = [
            ("auto", "auto"),
            ("required", "required"),
            ("none", "none"),
            ("get_weather", {"type": "function", "name": "get_weather"}),
            ("web_search", {"type": "web_search"}),
            (MCPToolChoice(server_label="test", name="tool"), {"server_label": "test", "type": "mcp", "name": "tool"})
        ]

        for tool_choice, expected in test_cases:
            settings = ModelSettings(tool_choice=tool_choice)

            await streaming_model.get_response(
                system_instructions="Test",
                input="Hello",
                model_settings=settings,
                tools=[sample_function_tool],
                output_schema=None,
                handoffs=[],
                tracing=None,
                task_id=sample_task_id
            )

            create_call = streaming_model.client.responses.create.call_args
            assert create_call.kwargs['tool_choice'] == expected

    @pytest.mark.asyncio
    async def test_parallel_tool_calls(self, streaming_model, _mock_adk_streaming, sample_task_id, sample_function_tool):
        """Test parallel tool calls setting"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        for parallel in [True, False]:
            settings = ModelSettings(parallel_tool_calls=parallel)

            await streaming_model.get_response(
                system_instructions="Test",
                input="Hello",
                model_settings=settings,
                tools=[sample_function_tool],
                output_schema=None,
                handoffs=[],
                tracing=None,
                task_id=sample_task_id
            )

            create_call = streaming_model.client.responses.create.call_args
            assert create_call.kwargs['parallel_tool_calls'] == parallel

    @pytest.mark.asyncio
    async def test_truncation_strategy(self, streaming_model, _mock_adk_streaming, sample_task_id):
        """Test truncation parameter"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        # truncation now accepts 'auto' or 'disabled' string literals
        settings = ModelSettings(truncation="auto")

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=settings,
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        assert create_call.kwargs['truncation'] == "auto"

    @pytest.mark.asyncio
    async def test_response_include(self, streaming_model, _mock_adk_streaming, sample_task_id, sample_file_search_tool):
        """Test response include parameter"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        settings = ModelSettings(
            response_include=["reasoning.encrypted_content", "message.output_text.logprobs"]
        )

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=settings,
            tools=[sample_file_search_tool],  # This adds file_search_call.results
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        include_list = create_call.kwargs['include']
        assert "reasoning.encrypted_content" in include_list
        assert "message.output_text.logprobs" in include_list
        assert "file_search_call.results" in include_list  # Added by file search tool

    @pytest.mark.asyncio
    async def test_verbosity(self, streaming_model, _mock_adk_streaming, sample_task_id):
        """Test verbosity settings"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        settings = ModelSettings(verbosity="high")

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=settings,
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        assert create_call.kwargs['text'] == {"verbosity": "high"}

    @pytest.mark.asyncio
    async def test_metadata_and_store(self, streaming_model, _mock_adk_streaming, sample_task_id):
        """Test metadata and store parameters"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        metadata = {"user_id": "123", "session": "abc"}
        store = True

        settings = ModelSettings(
            metadata=metadata,
            store=store
        )

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=settings,
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        assert create_call.kwargs['metadata'] == metadata
        assert create_call.kwargs['store'] == store

    @pytest.mark.asyncio
    async def test_extra_headers_and_body(self, streaming_model, _mock_adk_streaming, sample_task_id):
        """Test extra customization parameters"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        extra_headers = {"X-Custom": "header"}
        extra_body = {"custom_field": "value"}
        extra_query = {"param": "value"}

        settings = ModelSettings(
            extra_headers=extra_headers,
            extra_body=extra_body,
            extra_query=extra_query
        )

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=settings,
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        assert create_call.kwargs['extra_headers'] == extra_headers
        assert create_call.kwargs['extra_body'] == extra_body
        assert create_call.kwargs['extra_query'] == extra_query

    @pytest.mark.asyncio
    async def test_top_logprobs(self, streaming_model, _mock_adk_streaming, sample_task_id):
        """Test top_logprobs parameter"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        settings = ModelSettings(top_logprobs=5)

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=settings,
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        # top_logprobs goes into extra_args
        assert "top_logprobs" in create_call.kwargs
        assert create_call.kwargs['top_logprobs'] == 5
        # Also should add to include list
        assert "message.output_text.logprobs" in create_call.kwargs['include']


class TestStreamingModelTools:
    """Test that all tool types work with streaming"""

    @pytest.mark.asyncio
    async def test_function_tool(self, streaming_model, _mock_adk_streaming, sample_task_id, sample_function_tool):
        """Test FunctionTool conversion and streaming"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[sample_function_tool],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'function'
        assert tools[0]['name'] == 'get_weather'
        assert tools[0]['description'] == 'Get the current weather'
        assert 'parameters' in tools[0]

    @pytest.mark.asyncio
    async def test_web_search_tool(self, streaming_model, _mock_adk_streaming, sample_task_id, sample_web_search_tool):
        """Test WebSearchTool conversion"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[sample_web_search_tool],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'web_search'

    @pytest.mark.asyncio
    async def test_file_search_tool(self, streaming_model, _mock_adk_streaming, sample_task_id, sample_file_search_tool):
        """Test FileSearchTool conversion"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[sample_file_search_tool],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'file_search'
        assert tools[0]['vector_store_ids'] == ['vs_123']
        assert tools[0]['max_num_results'] == 10

    @pytest.mark.asyncio
    async def test_computer_tool(self, streaming_model, _mock_adk_streaming, sample_task_id, sample_computer_tool):
        """Test ComputerTool conversion"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[sample_computer_tool],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'computer_use_preview'
        assert tools[0]['environment'] == 'desktop'
        assert tools[0]['display_width'] == 1920
        assert tools[0]['display_height'] == 1080

    @pytest.mark.asyncio
    async def test_multiple_computer_tools_error(self, streaming_model, _mock_adk_streaming, sample_task_id, sample_computer_tool):
        """Test that multiple computer tools raise an error"""
        streaming_model.client.responses.create = AsyncMock()

        # Create two computer tools
        computer2 = MagicMock()
        computer2.environment = "mobile"
        computer2.dimensions = [375, 812]
        from agents.tool import ComputerTool
        second_computer_tool = ComputerTool(computer=computer2)

        with pytest.raises(ValueError, match="You can only provide one computer tool"):
            await streaming_model.get_response(
                system_instructions="Test",
                input="Hello",
                model_settings=ModelSettings(),
                tools=[sample_computer_tool, second_computer_tool],
                output_schema=None,
                handoffs=[],
                tracing=None,
                task_id=sample_task_id
            )

    @pytest.mark.asyncio
    async def test_hosted_mcp_tool(self, streaming_model, _mock_adk_streaming, sample_task_id, sample_hosted_mcp_tool):
        """Test HostedMCPTool conversion"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[sample_hosted_mcp_tool],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'mcp'
        assert tools[0]['server_label'] == 'test_server'

    @pytest.mark.asyncio
    async def test_image_generation_tool(self, streaming_model, _mock_adk_streaming, sample_task_id, sample_image_generation_tool):
        """Test ImageGenerationTool conversion"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[sample_image_generation_tool],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'image_generation'

    @pytest.mark.asyncio
    async def test_code_interpreter_tool(self, streaming_model, _mock_adk_streaming, sample_task_id, sample_code_interpreter_tool):
        """Test CodeInterpreterTool conversion"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[sample_code_interpreter_tool],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'code_interpreter'

    @pytest.mark.asyncio
    async def test_local_shell_tool(self, streaming_model, _mock_adk_streaming, sample_task_id, sample_local_shell_tool):
        """Test LocalShellTool conversion"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[sample_local_shell_tool],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'local_shell'
        # working_directory no longer in API - LocalShellTool uses executor internally

    @pytest.mark.asyncio
    async def test_handoffs(self, streaming_model, _mock_adk_streaming, sample_task_id, sample_handoff):
        """Test Handoff conversion to function tools"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[sample_handoff],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'function'
        assert tools[0]['name'] == 'transfer_to_support'
        assert tools[0]['description'] == 'Transfer to support agent'

    @pytest.mark.asyncio
    async def test_mixed_tools(self, streaming_model, _mock_adk_streaming, sample_task_id,
                              sample_function_tool, sample_web_search_tool, sample_handoff):
        """Test multiple tools together"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[sample_function_tool, sample_web_search_tool],
            output_schema=None,
            handoffs=[sample_handoff],
            tracing=None,
            task_id=sample_task_id
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 3  # 2 tools + 1 handoff

        # Check each tool type is present
        tool_types = [t['type'] for t in tools]
        assert 'function' in tool_types  # function tool and handoff
        assert 'web_search' in tool_types


class TestStreamingModelBasics:
    """Test core streaming functionality"""

    @pytest.mark.asyncio
    async def test_responses_api_streaming(self, streaming_model, mock_adk_streaming, sample_task_id):
        """Test basic Responses API streaming flow"""
        streaming_model.client.responses.create = AsyncMock()

        # Create a mock stream with text deltas
        mock_stream = AsyncMock()
        events = [
            MagicMock(type="response.output_item.added", item=MagicMock(type="message")),
            MagicMock(type="response.text.delta", delta="Hello "),
            MagicMock(type="response.text.delta", delta="world!"),
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ]
        mock_stream.__aiter__.return_value = iter(events)
        streaming_model.client.responses.create.return_value = mock_stream

        result = await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        # Verify streaming context was created
        mock_adk_streaming.streaming_task_message_context.assert_called_with(
            task_id=sample_task_id,
            initial_content=mock_adk_streaming.streaming_task_message_context.call_args.kwargs['initial_content']
        )

        # Verify result is returned as ModelResponse
        from agents import ModelResponse
        assert isinstance(result, ModelResponse)

    @pytest.mark.asyncio
    async def test_task_id_threading(self, streaming_model, mock_adk_streaming):
        """Test that task_id is properly threaded through to streaming context"""
        streaming_model.client.responses.create = AsyncMock()

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ])
        streaming_model.client.responses.create.return_value = mock_stream

        task_id = "test_task_12345"

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=task_id
        )

        # Verify task_id was passed to streaming context
        mock_adk_streaming.streaming_task_message_context.assert_called()
        call_args = mock_adk_streaming.streaming_task_message_context.call_args
        assert call_args.kwargs['task_id'] == task_id

    @pytest.mark.asyncio
    async def test_redis_context_creation(self, streaming_model, mock_adk_streaming, sample_task_id):
        """Test that Redis streaming contexts are created properly"""
        streaming_model.client.responses.create = AsyncMock()

        # Mock stream with reasoning
        mock_stream = AsyncMock()
        events = [
            MagicMock(type="response.output_item.added", item=MagicMock(type="reasoning")),
            MagicMock(type="response.reasoning_summary_text.delta", delta="Thinking...", summary_index=0),
            MagicMock(type="response.completed", response=MagicMock(output=[]))
        ]
        mock_stream.__aiter__.return_value = iter(events)
        streaming_model.client.responses.create.return_value = mock_stream

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(reasoning=Reasoning(effort="medium")),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
            task_id=sample_task_id
        )

        # Should create at least one context for reasoning
        assert mock_adk_streaming.streaming_task_message_context.call_count >= 1

    @pytest.mark.asyncio
    async def test_missing_task_id_error(self, streaming_model):
        """Test that missing task_id raises appropriate error"""
        streaming_model.client.responses.create = AsyncMock()

        with pytest.raises(ValueError, match="task_id is required"):
            await streaming_model.get_response(
                system_instructions="Test",
                input="Hello",
                model_settings=ModelSettings(),
                tools=[],
                output_schema=None,
                handoffs=[],
                tracing=None,
                task_id=None  # Missing task_id
            )