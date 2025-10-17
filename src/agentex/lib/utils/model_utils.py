from __future__ import annotations

from typing import Any, TypeVar
from datetime import datetime
from collections.abc import Mapping, Iterable

from pydantic import BaseModel as PydanticBaseModel, ConfigDict

from agentex.lib.utils.io import load_yaml_file

T = TypeVar("T", bound="BaseModel")


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_yaml(cls: type[T], file_path: str) -> T:
        """
        Returns an instance of this class by deserializing from a YAML file.

        :param file_path: The path to the YAML file.
        :return: An instance of this class.
        """
        yaml_dict = load_yaml_file(file_path=file_path)
        class_object = cls.model_validate(yaml_dict)
        return class_object

    def to_json(self, *args, **kwargs) -> str:
        return self.model_dump_json(*args, **kwargs)

    def to_dict(self, *_args, **_kwargs) -> dict[str, Any]:
        return recursive_model_dump(self)


def recursive_model_dump(obj: Any) -> Any:
    if isinstance(obj, PydanticBaseModel):
        # Get the model data as dict and recursively process each field
        # This allows us to handle non-serializable objects like functions
        try:
            return obj.model_dump(mode="json")
        except Exception:
            # If model_dump fails (e.g., due to functions), manually process
            model_dict = {}
            for field_name in obj.__class__.model_fields:
                field_value = getattr(obj, field_name)
                model_dict[field_name] = recursive_model_dump(field_value)
            return model_dict
    elif isinstance(obj, datetime):
        # Serialize datetime to ISO format string
        return obj.isoformat()
    elif callable(obj):
        # Serialize functions and other callable objects
        if hasattr(obj, "__name__"):
            func_name = obj.__name__
        else:
            func_name = str(obj)

        if hasattr(obj, "__module__"):
            return f"<function {obj.__module__}.{func_name}>"
        else:
            return f"<function {func_name}>"
    elif isinstance(obj, Mapping):
        # Recursively serialize dictionary values
        return {k: recursive_model_dump(v) for k, v in obj.items()}
    elif isinstance(obj, Iterable) and not isinstance(obj, str | bytes):
        # Recursively serialize items in lists, tuples, sets, etc.
        return [recursive_model_dump(item) for item in obj]
    else:
        # Return primitive types as-is
        return obj
