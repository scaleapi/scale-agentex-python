# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union
from typing_extensions import Required, TypeAlias, TypedDict

from ..data_content_param import DataContentParam
from ..text_content_param import TextContentParam
from ..tool_request_content_param import ToolRequestContentParam
from ..tool_response_content_param import ToolResponseContentParam

__all__ = ["BatchUpdateParams", "Updates"]


class BatchUpdateParams(TypedDict, total=False):
    task_id: Required[str]

    updates: Required[Dict[str, Updates]]


Updates: TypeAlias = Union[TextContentParam, DataContentParam, ToolRequestContentParam, ToolResponseContentParam]
