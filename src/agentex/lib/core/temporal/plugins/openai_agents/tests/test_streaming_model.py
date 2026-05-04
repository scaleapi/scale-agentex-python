"""
Comprehensive tests for StreamingModel with all configurations and tool types.
"""

from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from agents import ModelSettings
from openai import NOT_GIVEN
from agents.model_settings import Reasoning, MCPToolChoice  # type: ignore[attr-defined]
from openai.types.responses import (
    ResponseCompletedEvent,
    ResponseTextDeltaEvent,
    ResponseOutputItemAddedEvent,
    ResponseReasoningSummaryTextDeltaEvent,
)


class TestStreamingModelSettings:
    """Test that all ModelSettings parameters work with Responses API"""

    @pytest.mark.asyncio
    async def test_temperature_setting(self, streaming_model, _streaming_context_vars):
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
            )

            # Verify temperature was passed correctly
            create_call = streaming_model.client.responses.create.call_args
            assert create_call.kwargs['temperature'] == temp

    @pytest.mark.asyncio
    async def test_top_p_setting(self, streaming_model, _streaming_context_vars):
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
            )

            create_call = streaming_model.client.responses.create.call_args
            expected = top_p if top_p is not None else NOT_GIVEN
            assert create_call.kwargs['top_p'] == expected

    @pytest.mark.asyncio
    async def test_max_tokens_setting(self, streaming_model, _streaming_context_vars):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        assert create_call.kwargs['max_output_tokens'] == 2000

    @pytest.mark.asyncio
    async def test_reasoning_effort_settings(self, streaming_model, _streaming_context_vars):
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
            )

            create_call = streaming_model.client.responses.create.call_args
            assert create_call.kwargs['reasoning'] == {"effort": effort}

    @pytest.mark.asyncio
    async def test_reasoning_summary_settings(self, streaming_model, _streaming_context_vars):
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
            )

            create_call = streaming_model.client.responses.create.call_args
            assert create_call.kwargs['reasoning'] == {"effort": "medium", "summary": summary}

    @pytest.mark.asyncio
    async def test_tool_choice_variations(self, streaming_model, _streaming_context_vars, sample_function_tool):
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
            )

            create_call = streaming_model.client.responses.create.call_args
            assert create_call.kwargs['tool_choice'] == expected

    @pytest.mark.asyncio
    async def test_parallel_tool_calls(self, streaming_model, _streaming_context_vars, sample_function_tool):
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
            )

            create_call = streaming_model.client.responses.create.call_args
            assert create_call.kwargs['parallel_tool_calls'] == parallel

    @pytest.mark.asyncio
    async def test_truncation_strategy(self, streaming_model, _streaming_context_vars):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        assert create_call.kwargs['truncation'] == "auto"

    @pytest.mark.asyncio
    async def test_response_include(self, streaming_model, _streaming_context_vars, sample_file_search_tool):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        include_list = create_call.kwargs['include']
        assert "reasoning.encrypted_content" in include_list
        assert "message.output_text.logprobs" in include_list
        assert "file_search_call.results" in include_list  # Added by file search tool

    @pytest.mark.asyncio
    async def test_verbosity(self, streaming_model, _streaming_context_vars):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        assert create_call.kwargs['text'] == {"verbosity": "high"}

    @pytest.mark.asyncio
    async def test_metadata_and_store(self, streaming_model, _streaming_context_vars):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        assert create_call.kwargs['metadata'] == metadata
        assert create_call.kwargs['store'] == store

    @pytest.mark.asyncio
    async def test_extra_headers_and_body(self, streaming_model, _streaming_context_vars):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        assert create_call.kwargs['extra_headers'] == extra_headers
        assert create_call.kwargs['extra_body'] == extra_body
        assert create_call.kwargs['extra_query'] == extra_query

    @pytest.mark.asyncio
    async def test_top_logprobs(self, streaming_model, _streaming_context_vars):
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
    async def test_function_tool(self, streaming_model, _streaming_context_vars, sample_function_tool):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'function'
        assert tools[0]['name'] == 'get_weather'
        assert tools[0]['description'] == 'Get the current weather'
        assert 'parameters' in tools[0]

    @pytest.mark.asyncio
    async def test_web_search_tool(self, streaming_model, _streaming_context_vars, sample_web_search_tool):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'web_search'

    @pytest.mark.asyncio
    async def test_file_search_tool(self, streaming_model, _streaming_context_vars, sample_file_search_tool):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'file_search'
        assert tools[0]['vector_store_ids'] == ['vs_123']
        assert tools[0]['max_num_results'] == 10

    @pytest.mark.asyncio
    async def test_computer_tool(self, streaming_model, _streaming_context_vars, sample_computer_tool):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'computer_use_preview'
        assert tools[0]['environment'] == 'desktop'
        assert tools[0]['display_width'] == 1920
        assert tools[0]['display_height'] == 1080

    @pytest.mark.asyncio
    async def test_multiple_computer_tools_error(self, streaming_model, _streaming_context_vars, sample_computer_tool):
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
            )

    @pytest.mark.asyncio
    async def test_hosted_mcp_tool(self, streaming_model, _streaming_context_vars, sample_hosted_mcp_tool):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'mcp'
        assert tools[0]['server_label'] == 'test_server'

    @pytest.mark.asyncio
    async def test_image_generation_tool(self, streaming_model, _streaming_context_vars, sample_image_generation_tool):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'image_generation'

    @pytest.mark.asyncio
    async def test_code_interpreter_tool(self, streaming_model, _streaming_context_vars, sample_code_interpreter_tool):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'code_interpreter'

    @pytest.mark.asyncio
    async def test_local_shell_tool(self, streaming_model, _streaming_context_vars, sample_local_shell_tool):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'local_shell'
        # working_directory no longer in API - LocalShellTool uses executor internally

    @pytest.mark.asyncio
    async def test_handoffs(self, streaming_model, _streaming_context_vars, sample_handoff):
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
        )

        create_call = streaming_model.client.responses.create.call_args
        tools = create_call.kwargs['tools']
        assert len(tools) == 1
        assert tools[0]['type'] == 'function'
        assert tools[0]['name'] == 'transfer_to_support'
        assert tools[0]['description'] == 'Transfer to support agent'

    @pytest.mark.asyncio
    async def test_mixed_tools(self, streaming_model, _streaming_context_vars,
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
    async def test_responses_api_streaming(self, streaming_model, mock_adk_streaming, _streaming_context_vars, sample_task_id):
        """Test basic Responses API streaming flow"""
        streaming_model.client.responses.create = AsyncMock()

        # Production uses ``isinstance(event, ...)`` against the OpenAI Responses
        # event types to dispatch. ``spec=...`` makes isinstance pass without
        # triggering pydantic validation on partially-constructed events.
        item_added = MagicMock(spec=ResponseOutputItemAddedEvent)
        item_added.item = MagicMock(type="message")
        item_added.output_index = 0
        text_delta_1 = MagicMock(spec=ResponseTextDeltaEvent)
        text_delta_1.delta = "Hello "
        text_delta_2 = MagicMock(spec=ResponseTextDeltaEvent)
        text_delta_2.delta = "world!"
        completed = MagicMock(spec=ResponseCompletedEvent)
        completed.response = MagicMock(output=[], usage=MagicMock(), id=None)
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([item_added, text_delta_1, text_delta_2, completed])
        streaming_model.client.responses.create.return_value = mock_stream

        result = await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
        )

        # Verify streaming context was created with the right task_id. We
        # don't strict-match the full kwargs because production also passes
        # ``streaming_mode``, which is an implementation detail this test
        # doesn't care about.
        mock_adk_streaming.streaming_task_message_context.assert_called()
        call_kwargs = mock_adk_streaming.streaming_task_message_context.call_args.kwargs
        assert call_kwargs['task_id'] == sample_task_id

        # Verify result is returned as ModelResponse
        from agents import ModelResponse
        assert isinstance(result, ModelResponse)

    @pytest.mark.asyncio
    async def test_task_id_threading(self, streaming_model, mock_adk_streaming, _streaming_context_vars):
        """Test that task_id from the streaming ContextVar is threaded through to
        the streaming context. ``_streaming_context_vars`` yields the task_id that
        was set on the ContextVar, which is what production reads (the kwarg
        ``task_id=...`` to ``get_response`` is swallowed by ``**kwargs`` and ignored).
        """
        streaming_model.client.responses.create = AsyncMock()

        item_added = MagicMock(spec=ResponseOutputItemAddedEvent)
        item_added.item = MagicMock(type="message")
        item_added.output_index = 0
        completed = MagicMock(spec=ResponseCompletedEvent)
        completed.response = MagicMock(output=[], usage=MagicMock(), id=None)
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([item_added, completed])
        streaming_model.client.responses.create.return_value = mock_stream

        expected_task_id = _streaming_context_vars

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
        )

        # Verify the ContextVar's task_id was threaded through to the streaming context
        mock_adk_streaming.streaming_task_message_context.assert_called()
        call_args = mock_adk_streaming.streaming_task_message_context.call_args
        assert call_args.kwargs['task_id'] == expected_task_id

    @pytest.mark.asyncio
    async def test_redis_context_creation(self, streaming_model, mock_adk_streaming, _streaming_context_vars):
        """Test that Redis streaming contexts are created properly"""
        streaming_model.client.responses.create = AsyncMock()

        # Production uses ``isinstance`` against OpenAI Responses event types;
        # ``spec=...`` makes isinstance pass without triggering pydantic validation.
        item_added = MagicMock(spec=ResponseOutputItemAddedEvent)
        item_added.item = MagicMock(type="reasoning")
        item_added.output_index = 0
        reasoning_delta = MagicMock(spec=ResponseReasoningSummaryTextDeltaEvent)
        reasoning_delta.delta = "Thinking..."
        reasoning_delta.summary_index = 0
        completed = MagicMock(spec=ResponseCompletedEvent)
        completed.response = MagicMock(output=[], usage=MagicMock(), id=None)
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter([item_added, reasoning_delta, completed])
        streaming_model.client.responses.create.return_value = mock_stream

        await streaming_model.get_response(
            system_instructions="Test",
            input="Hello",
            model_settings=ModelSettings(reasoning=Reasoning(effort="medium")),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
        )

        # Should create at least one context for reasoning
        assert mock_adk_streaming.streaming_task_message_context.call_count >= 1

    @pytest.mark.asyncio
    async def test_missing_task_id_error(self, streaming_model):
        """Test that missing streaming ContextVars raise an appropriate error.

        Production reads task_id, trace_id, and parent_span_id from ContextVars
        populated by ContextInterceptor. Without ``_streaming_context_vars``
        requested, all three are at their defaults — empty strings — and
        ``get_response`` raises before doing any work.
        """
        streaming_model.client.responses.create = AsyncMock()

        with pytest.raises(ValueError, match=r"task_id.*required"):
            await streaming_model.get_response(
                system_instructions="Test",
                input="Hello",
                model_settings=ModelSettings(),
                tools=[],
                output_schema=None,
                handoffs=[],
                tracing=None,
            )


class TestStreamingModelUsageResponseIdAndCacheKey:
    """Cover real-Usage capture, real response_id, span emission, and opt-in prompt_cache_key."""

    @staticmethod
    def _async_iter(events):
        async def _gen():
            for event in events:
                yield event
        return _gen()

    @staticmethod
    def _make_response_completed_event(
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        cached_tokens: int = 0,
        reasoning_tokens: int = 0,
        with_usage: bool = True,
        response_id: Optional[str] = "resp_real_server_id",
    ):
        usage = MagicMock()
        usage.input_tokens = input_tokens
        usage.output_tokens = output_tokens
        usage.total_tokens = total_tokens
        usage.input_tokens_details = MagicMock(cached_tokens=cached_tokens)
        usage.output_tokens_details = MagicMock(reasoning_tokens=reasoning_tokens)

        response = MagicMock()
        response.output = []
        response.usage = usage if with_usage else None
        response.id = response_id

        event = MagicMock(spec=ResponseCompletedEvent)
        event.response = response
        return event

    @pytest.fixture
    def mock_span(self):
        return MagicMock()

    @pytest.fixture
    def streaming_model_with_mock_tracer(self, streaming_model, mock_span):
        """A streaming_model whose tracer.trace().span(...) yields a captured mock span."""
        async_cm = MagicMock()
        async_cm.__aenter__ = AsyncMock(return_value=mock_span)
        async_cm.__aexit__ = AsyncMock(return_value=False)
        trace_obj = MagicMock()
        trace_obj.span = MagicMock(return_value=async_cm)
        streaming_model.tracer = MagicMock()
        streaming_model.tracer.trace = MagicMock(return_value=trace_obj)
        return streaming_model

    @pytest.mark.asyncio
    async def test_usage_captured_from_completed_event(
        self,
        streaming_model_with_mock_tracer,
        _streaming_context_vars,  # noqa: ARG002
    ):
        model = streaming_model_with_mock_tracer
        completed = self._make_response_completed_event(
            input_tokens=1234, output_tokens=56, total_tokens=1290,
            cached_tokens=987, reasoning_tokens=42,
        )
        model.client.responses.create = AsyncMock(return_value=self._async_iter([completed]))

        response = await model.get_response(
            system_instructions=None,
            input="hi",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
        )

        assert response.usage.input_tokens == 1234
        assert response.usage.output_tokens == 56
        assert response.usage.total_tokens == 1290
        assert response.usage.input_tokens_details.cached_tokens == 987
        assert response.usage.output_tokens_details.reasoning_tokens == 42

    @pytest.mark.asyncio
    async def test_usage_falls_back_when_no_completed_event(
        self,
        streaming_model_with_mock_tracer,
        _streaming_context_vars,  # noqa: ARG002
    ):
        """Stream ending without a ResponseCompletedEvent (error path) → zero Usage."""
        model = streaming_model_with_mock_tracer
        model.client.responses.create = AsyncMock(return_value=self._async_iter([]))

        response = await model.get_response(
            system_instructions=None,
            input="hi",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
        )

        assert response.usage.input_tokens == 0
        assert response.usage.output_tokens == 0
        assert response.usage.total_tokens == 0
        assert response.usage.input_tokens_details.cached_tokens == 0
        assert response.usage.output_tokens_details.reasoning_tokens == 0

    @pytest.mark.asyncio
    async def test_usage_emitted_in_span_output(
        self,
        streaming_model_with_mock_tracer,
        _streaming_context_vars,  # noqa: ARG002
        mock_span,
    ):
        model = streaming_model_with_mock_tracer
        completed = self._make_response_completed_event(
            input_tokens=100, output_tokens=10, total_tokens=110,
            cached_tokens=80, reasoning_tokens=5,
        )
        model.client.responses.create = AsyncMock(return_value=self._async_iter([completed]))

        await model.get_response(
            system_instructions=None,
            input="hi",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
        )

        assert isinstance(mock_span.output, dict)
        usage_block = mock_span.output["usage"]
        assert usage_block == {
            "input_tokens": 100,
            "output_tokens": 10,
            "total_tokens": 110,
            "cached_input_tokens": 80,
            "reasoning_tokens": 5,
        }

    @pytest.mark.asyncio
    async def test_response_id_captured_from_completed_event(
        self,
        streaming_model_with_mock_tracer,
        _streaming_context_vars,  # noqa: ARG002
    ):
        """Real server-issued id flows back on ModelResponse.response_id."""
        model = streaming_model_with_mock_tracer
        completed = self._make_response_completed_event(response_id="resp_abcdef123456")
        model.client.responses.create = AsyncMock(return_value=self._async_iter([completed]))

        response = await model.get_response(
            system_instructions=None,
            input="hi",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
        )

        assert response.response_id == "resp_abcdef123456"

    @pytest.mark.asyncio
    async def test_response_id_is_none_when_no_completed_event(
        self,
        streaming_model_with_mock_tracer,
        _streaming_context_vars,  # noqa: ARG002
    ):
        """Stream ending without ResponseCompletedEvent → response_id is None.

        Critical: must NOT fabricate a UUID. Returning a fake id would cause
        downstream `previous_response_id` chaining to 400 against the server.
        """
        model = streaming_model_with_mock_tracer
        model.client.responses.create = AsyncMock(return_value=self._async_iter([]))

        response = await model.get_response(
            system_instructions=None,
            input="hi",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
        )

        assert response.response_id is None

    @pytest.mark.asyncio
    async def test_prompt_cache_key_not_sent_by_default(
        self,
        streaming_model_with_mock_tracer,
        _streaming_context_vars,  # noqa: ARG002
    ):
        """Without an opt-in, prompt_cache_key resolves to NOT_GIVEN (omitted from request)."""
        model = streaming_model_with_mock_tracer
        completed = self._make_response_completed_event()
        model.client.responses.create = AsyncMock(return_value=self._async_iter([completed]))

        await model.get_response(
            system_instructions=None,
            input="hi",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
        )

        kwargs = model.client.responses.create.call_args.kwargs
        assert kwargs["prompt_cache_key"] is NOT_GIVEN

    @pytest.mark.asyncio
    async def test_prompt_cache_key_forwarded_when_opted_in(
        self,
        streaming_model_with_mock_tracer,
        _streaming_context_vars,  # noqa: ARG002
    ):
        """Caller opt-in via model_settings.extra_args is forwarded to responses.create."""
        model = streaming_model_with_mock_tracer
        completed = self._make_response_completed_event()
        model.client.responses.create = AsyncMock(return_value=self._async_iter([completed]))

        await model.get_response(
            system_instructions=None,
            input="hi",
            model_settings=ModelSettings(extra_args={"prompt_cache_key": "my-key"}),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
        )

        kwargs = model.client.responses.create.call_args.kwargs
        assert kwargs["prompt_cache_key"] == "my-key"
        # Must be popped from extra_args so the SDK doesn't see it twice.
        assert list(kwargs).count("prompt_cache_key") == 1

    @pytest.mark.asyncio
    async def test_previous_response_id_not_sent_by_default(
        self,
        streaming_model_with_mock_tracer,
        _streaming_context_vars,  # noqa: ARG002
    ):
        """Without an opt-in, previous_response_id resolves to NOT_GIVEN.

        Critical for non-Responses-API-native backends (e.g. Claude-via-LiteLLM)
        where unknown fields on the request body could be rejected. NOT_GIVEN
        is filtered before serialization, so the field is omitted entirely.
        """
        model = streaming_model_with_mock_tracer
        completed = self._make_response_completed_event()
        model.client.responses.create = AsyncMock(return_value=self._async_iter([completed]))

        await model.get_response(
            system_instructions=None,
            input="hi",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
        )

        kwargs = model.client.responses.create.call_args.kwargs
        assert kwargs["previous_response_id"] is NOT_GIVEN

    @pytest.mark.asyncio
    async def test_previous_response_id_forwarded_via_sdk_kwarg(
        self,
        streaming_model_with_mock_tracer,
        _streaming_context_vars,  # noqa: ARG002
    ):
        """The SDK threads previous_response_id as a keyword arg per Model.get_response
        abstract contract. Verify it reaches responses.create instead of being silently
        swallowed (which was the prior behavior under **kwargs)."""
        model = streaming_model_with_mock_tracer
        completed = self._make_response_completed_event()
        model.client.responses.create = AsyncMock(return_value=self._async_iter([completed]))

        await model.get_response(
            system_instructions=None,
            input="hi",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
            previous_response_id="resp_prior_turn",
        )

        kwargs = model.client.responses.create.call_args.kwargs
        assert kwargs["previous_response_id"] == "resp_prior_turn"

    @pytest.mark.asyncio
    async def test_conversation_and_prompt_not_sent_by_default(
        self,
        streaming_model_with_mock_tracer,
        _streaming_context_vars,  # noqa: ARG002
    ):
        """Without an opt-in, conversation/prompt resolve to NOT_GIVEN.

        Same opt-in pattern as previous_response_id and prompt_cache_key — the
        wire request is unchanged for callers (and non-OpenAI backends) that
        don't supply these.
        """
        model = streaming_model_with_mock_tracer
        completed = self._make_response_completed_event()
        model.client.responses.create = AsyncMock(return_value=self._async_iter([completed]))

        await model.get_response(
            system_instructions=None,
            input="hi",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
        )

        kwargs = model.client.responses.create.call_args.kwargs
        assert kwargs["conversation"] is NOT_GIVEN
        assert kwargs["prompt"] is NOT_GIVEN

    @pytest.mark.asyncio
    async def test_conversation_id_forwarded_via_sdk_kwarg(
        self,
        streaming_model_with_mock_tracer,
        _streaming_context_vars,  # noqa: ARG002
    ):
        """The SDK abstract names this `conversation_id`; the Responses API
        endpoint kwarg is `conversation`. Caller passes a string id; we forward
        it as-is (the Conversation type accepts str)."""
        model = streaming_model_with_mock_tracer
        completed = self._make_response_completed_event()
        model.client.responses.create = AsyncMock(return_value=self._async_iter([completed]))

        await model.get_response(
            system_instructions=None,
            input="hi",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
            conversation_id="conv_abc123",
        )

        kwargs = model.client.responses.create.call_args.kwargs
        assert kwargs["conversation"] == "conv_abc123"

    @pytest.mark.asyncio
    async def test_prompt_forwarded_via_sdk_kwarg(
        self,
        streaming_model_with_mock_tracer,
        _streaming_context_vars,  # noqa: ARG002
    ):
        """ResponsePromptParam (a TypedDict for pre-built prompts) is forwarded
        as-is to responses.create."""
        model = streaming_model_with_mock_tracer
        completed = self._make_response_completed_event()
        model.client.responses.create = AsyncMock(return_value=self._async_iter([completed]))

        prompt_param = {"id": "prompt_test_id", "version": "1"}
        await model.get_response(
            system_instructions=None,
            input="hi",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=None,
            prompt=prompt_param,  # type: ignore[arg-type]
        )

        kwargs = model.client.responses.create.call_args.kwargs
        assert kwargs["prompt"] == prompt_param