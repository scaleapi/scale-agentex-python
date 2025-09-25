import json
from datetime import datetime

from pydantic import BaseModel

from agentex.lib.utils.model_utils import recursive_model_dump


class SampleModel(BaseModel):
    """Sample model for testing recursive_model_dump functionality."""

    name: str
    value: int


def sample_function():
    """A sample function for testing function serialization."""
    return "test"


def another_function(x: int) -> str:
    """Another sample function with parameters."""
    return str(x)


class TestRecursiveModelDump:
    """Test cases for the recursive_model_dump function."""

    def test_pydantic_model_serialization(self):
        """Test that Pydantic models are properly serialized."""
        model = SampleModel(name="test", value=42)
        result = recursive_model_dump(model)

        assert isinstance(result, dict)
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_datetime_serialization(self):
        """Test that datetime objects are serialized to ISO format."""
        dt = datetime(2023, 12, 25, 10, 30, 45)
        result = recursive_model_dump(dt)

        assert isinstance(result, str)
        assert result == "2023-12-25T10:30:45"

    def test_function_serialization(self):
        """Test that functions are properly serialized to string representation."""
        result = recursive_model_dump(sample_function)

        assert isinstance(result, str)
        assert result.startswith("<function")
        assert "sample_function" in result
        # module name should be included
        assert "test_model_utils" in result

    def test_function_without_module_serialization(self):
        """Test function serialization when module info is not available."""

        # Create a lambda function which might not have __module__
        def lambda_like_func(x: int) -> int:
            return x * 2

        result = recursive_model_dump(lambda_like_func)

        assert isinstance(result, str)
        assert result.startswith("<function")

    def test_callable_object_serialization(self):
        """Test that callable objects (not just functions) are serialized."""

        class CallableClass:
            def __call__(self):
                return "called"

        callable_obj = CallableClass()
        result = recursive_model_dump(callable_obj)

        assert isinstance(result, str)
        assert result.startswith("<function")

    def test_dictionary_serialization(self):
        """Test that dictionaries are recursively serialized."""
        data = {
            "string": "value",
            "number": 42,
            "function": sample_function,
            "model": SampleModel(name="nested", value=100),
            "datetime": datetime(2023, 1, 1),
        }

        result = recursive_model_dump(data)

        assert isinstance(result, dict)
        assert result["string"] == "value"
        assert result["number"] == 42
        assert isinstance(result["function"], str)
        assert "<function" in result["function"]
        assert isinstance(result["model"], dict)
        assert result["model"]["name"] == "nested"
        assert result["datetime"] == "2023-01-01T00:00:00"

    def test_list_serialization(self):
        """Test that lists are recursively serialized."""
        data = [
            "string",
            42,
            sample_function,
            SampleModel(name="in_list", value=200),
            datetime(2023, 6, 15),
        ]

        result = recursive_model_dump(data)

        assert isinstance(result, list)
        assert result[0] == "string"
        assert result[1] == 42
        assert isinstance(result[2], str)
        assert "<function" in result[2]
        assert isinstance(result[3], dict)
        assert result[3]["name"] == "in_list"
        assert result[4] == "2023-06-15T00:00:00"

    def test_nested_structure_serialization(self):
        """Test complex nested structures with functions."""
        data = {
            "level1": {
                "level2": [
                    {
                        "function": another_function,
                        "model": SampleModel(name="deep", value=300),
                    }
                ]
            }
        }

        result = recursive_model_dump(data)

        assert isinstance(result, dict)
        nested_func: str = result["level1"]["level2"][0]["function"]  # type: ignore[assignment]
        assert isinstance(nested_func, str)
        assert "another_function" in nested_func

        nested_model: dict[str, object] = result["level1"]["level2"][0]["model"]  # type: ignore[assignment]
        assert nested_model["name"] == "deep"
        assert nested_model["value"] == 300

    def test_primitive_types_passthrough(self):
        """Test that primitive types are returned as-is."""
        primitives = ["string", 42, 3.14, True, False, None]

        for primitive in primitives:
            result = recursive_model_dump(primitive)
            assert result == primitive
            assert type(result) is type(primitive)

    def test_json_serializable_output(self):
        """Test output of recursive_model_dump is JSON serializable."""

        def nested_callable():
            return None

        complex_data = {
            "function": sample_function,
            "model": SampleModel(name="json_test", value=400),
            "datetime": datetime(2023, 3, 15, 14, 30),
            "list": [another_function, "string", 42],
            "nested": {"callable": nested_callable},
        }

        result = recursive_model_dump(complex_data)

        # This should not raise an exception
        json_str = json.dumps(result)

        # Verify we can parse it back
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert isinstance(parsed["function"], str)
        assert "<function" in parsed["function"]

    def test_base_model_to_dict_method(self):
        """Test that BaseModel can be serialized with recursive_model_dump."""
        model = SampleModel(name="to_dict_test", value=500)
        result = recursive_model_dump(model)

        assert isinstance(result, dict)
        assert result["name"] == "to_dict_test"
        assert result["value"] == 500

    def test_function_with_special_characters_in_name(self):
        """Test function serialization with special characters in names."""

        # Create a function with special characters (though this is unusual)
        def _special_func():
            return None

        result = recursive_model_dump(_special_func)

        assert isinstance(result, str)
        assert "_special_func" in result
        assert "<function" in result

    def test_pydantic_model_with_function_field(self):
        """Test that Pydantic models with functions are properly serialized."""

        class ModelWithFunction(BaseModel):
            name: str
            value: int
            callback: object  # Using object type to allow function

        def sample_callback():
            return "callback executed"

        model = ModelWithFunction(
            name="test_model", value=123, callback=sample_callback
        )

        # This should not raise an exception anymore
        result = recursive_model_dump(model)

        assert isinstance(result, dict)
        assert result["name"] == "test_model"
        assert result["value"] == 123
        assert isinstance(result["callback"], str)
        assert "<function" in result["callback"]
        assert "sample_callback" in result["callback"]
