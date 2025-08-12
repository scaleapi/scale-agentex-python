from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict

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

    def to_dict(self, *args, **kwargs) -> dict[str, Any]:
        return recursive_model_dump(self)


def recursive_model_dump(obj: Any) -> Any:
    if isinstance(obj, PydanticBaseModel):
        # Serialize BaseModel to dict
        return obj.model_dump(mode="json")
    elif isinstance(obj, datetime):
        # Serialize datetime to ISO format string
        return obj.isoformat()
    elif isinstance(obj, Mapping):
        # Recursively serialize dictionary values
        return {k: recursive_model_dump(v) for k, v in obj.items()}
    elif isinstance(obj, Iterable) and not isinstance(obj, str | bytes):
        # Recursively serialize items in lists, tuples, sets, etc.
        return [recursive_model_dump(item) for item in obj]
    else:
        # Return primitive types as-is
        return obj
