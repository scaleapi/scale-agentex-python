from __future__ import annotations

import json
from typing import Any, override

import pytest
from pydantic import ValidationError

from src.agentex.lib.core.temporal.activities.adk.providers.openai_activities import (  # type: ignore[import-untyped]
    FunctionTool,
)


def sample_handler(context, args: str) -> str:
    """Sample handler function for testing."""
    return f"Processed: {args}"


def complex_handler(context, args: str) -> dict[str, Any]:
    """More complex handler that returns structured data."""
    parsed_args = json.loads(args) if args else {}
    return {
        "status": "success",
        "input": parsed_args,
        "context_info": str(type(context)),
    }


class TestFunctionTool:
    """Test cases for FunctionTool serialization with JSON."""

    def test_basic_serialization_with_json(self):
        """Test that FunctionTool can be serialized and deserialized with JSON."""
        # Create a FunctionTool with a callable
        tool = FunctionTool(
            name="test_tool",
            description="A test tool",
            params_json_schema={"type": "string"},
            strict_json_schema=True,
            is_enabled=True,
            on_invoke_tool=sample_handler,
        )

        # Serialize to JSON (this is what the caller will do)
        json_data = json.dumps(tool.model_dump())

        # Deserialize from JSON
        data = json.loads(json_data)
        new_tool = FunctionTool.model_validate(data)

        # Test that the callable is restored
        assert new_tool.on_invoke_tool is not None
        assert callable(new_tool.on_invoke_tool)

        # Test that the callable works as expected
        result = new_tool.on_invoke_tool(None, "test_input")
        assert result == "Processed: test_input"

    def test_complex_function_serialization(self):
        """Test serialization of more complex functions."""
        tool = FunctionTool(
            name="complex_tool",
            description="A complex test tool",
            params_json_schema={
                "type": "object",
                "properties": {"key": {"type": "string"}},
            },
            on_invoke_tool=complex_handler,
        )

        # Serialize and deserialize via JSON
        json_data = json.dumps(tool.model_dump())
        data = json.loads(json_data)
        new_tool = FunctionTool.model_validate(data)

        # Test the complex function
        test_input = '{"test": "value"}'
        result = new_tool.on_invoke_tool(None, test_input)

        assert result["status"] == "success"
        assert result["input"] == {"test": "value"}

    def test_none_callable_handling(self):
        """Test that passing None for callable raises an error."""
        # Test that None callable raises ValueError
        with pytest.raises(
            ValueError,
            match="One of `on_invoke_tool` or `on_invoke_tool_serialized` should be set",
        ):
            FunctionTool(
                name="empty_tool",
                description="Tool with no callable",
                params_json_schema={"type": "string"},
                on_invoke_tool=None,
            )

        # Test with valid function - this should work
        tool_func = FunctionTool(
            name="func_tool",
            description="Tool with function",
            params_json_schema={"type": "string"},
            on_invoke_tool=sample_handler,
        )
        assert tool_func.on_invoke_tool is not None

    def test_lambda_function_serialization(self):
        """Test that lambda functions can be serialized."""
        # Set a lambda function
        tool = FunctionTool(
            name="lambda_tool",
            description="Tool with lambda",
            params_json_schema={"type": "string"},
            on_invoke_tool=lambda ctx, args: f"Lambda result: {args}",
        )

        # Serialize and deserialize via JSON
        json_data = json.dumps(tool.model_dump())
        data = json.loads(json_data)
        new_tool = FunctionTool.model_validate(data)

        # Test that the lambda works
        result = new_tool.on_invoke_tool(None, "test")
        assert result == "Lambda result: test"

    def test_closure_serialization(self):
        """Test that closures can be serialized."""

        def create_handler(prefix: str):
            def handler(context, args: str) -> str:
                return f"{prefix}: {args}"

            return handler

        # Set a closure
        tool = FunctionTool(
            name="closure_tool",
            description="Tool with closure",
            params_json_schema={"type": "string"},
            on_invoke_tool=create_handler("PREFIX"),
        )

        # Serialize and deserialize via JSON
        json_data = json.dumps(tool.model_dump())
        data = json.loads(json_data)
        new_tool = FunctionTool.model_validate(data)

        # Test that the closure works with captured variable
        result = new_tool.on_invoke_tool(None, "test")
        assert result == "PREFIX: test"

    def test_function_tool_with_none_handler_raises_error(self):
        """Test that trying to create tool with None handler raises error."""
        # Test that None callable raises ValueError
        with pytest.raises(
            ValueError,
            match="One of `on_invoke_tool` or `on_invoke_tool_serialized` should be set",
        ):
            FunctionTool(
                name="none_handler_test",
                description="Test tool with None handler",
                params_json_schema={"type": "string"},
                on_invoke_tool=None,
            )

    def test_to_oai_function_tool_with_valid_handler(self):
        """Test that to_oai_function_tool works with valid function."""
        tool = FunctionTool(
            name="valid_handler_test",
            description="Test tool with valid handler",
            params_json_schema={"type": "string"},
            on_invoke_tool=sample_handler,
        )

        # This should work when on_invoke_tool is set
        oai_tool = tool.to_oai_function_tool()

        # Verify the OAI tool was created successfully
        assert oai_tool is not None
        assert oai_tool.name == "valid_handler_test"
        assert oai_tool.description == "Test tool with valid handler"
        assert oai_tool.on_invoke_tool is not None
        assert callable(oai_tool.on_invoke_tool)

        # Test that the handler works through the OAI tool
        result = oai_tool.on_invoke_tool(None, "test_input")
        assert result == "Processed: test_input"

    def test_serialization_error_handling(self):
        """Test error handling when serialization fails."""

        # Try to create a FunctionTool with an unserializable callable
        class UnserializableCallable:
            def __call__(self, context, args):
                return "test"

            @override
            def __getstate__(self):
                raise Exception("Cannot serialize this object")

        unserializable = UnserializableCallable()

        # This should raise an Exception during construction (from the unserializable object)
        with pytest.raises(Exception, match="Cannot serialize this object"):
            FunctionTool(
                name="error_test_with_unserializable",
                description="Test error handling with unserializable",
                params_json_schema={"type": "string"},
                on_invoke_tool=unserializable,
            )

    def test_deserialization_error_handling(self):
        """Test error handling when deserialization fails."""

        # Create a tool and manually corrupt its serialized data to test deserialization error
        # First, create a valid tool
        valid_tool = FunctionTool(
            name="valid_tool",
            description="Valid tool for corruption",
            params_json_schema={"type": "string"},
            on_invoke_tool=sample_handler,
        )

        # Serialize it
        serialized_data = valid_tool.model_dump()

        # Corrupt the serialized callable data with invalid base64
        serialized_data["on_invoke_tool_serialized"] = (
            "invalid_base64_data!"  # Add invalid character
        )

        # This should raise an error during model validation due to invalid base64
        with pytest.raises((ValidationError, ValueError)):
            FunctionTool.model_validate(serialized_data)

    def test_full_roundtrip_with_serialization(self):
        """Test a full roundtrip with a single tool."""
        tool = FunctionTool(
            name="test_tool",
            description="Test tool for roundtrip",
            params_json_schema={"type": "string"},
            on_invoke_tool=lambda ctx, args: f"Tool result: {args}",
        )

        # Serialize tool to JSON
        json_data = json.dumps(tool.model_dump())

        # Deserialize from JSON
        data = json.loads(json_data)
        new_tool = FunctionTool.model_validate(data)

        # Test the tool
        result = new_tool.on_invoke_tool(None, "test")
        assert "Tool result: test" == result

        result = new_tool.to_oai_function_tool().on_invoke_tool(None, "test")
        assert "Tool result: test" == result
