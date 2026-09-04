# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List
from typing_extensions import TypeAlias

from ..task_message import TaskMessage

__all__ = ["BatchCreateResponse"]

BatchCreateResponse: TypeAlias = List[TaskMessage]
