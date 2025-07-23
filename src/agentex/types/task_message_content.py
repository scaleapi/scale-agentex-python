# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Union
from typing_extensions import Annotated, TypeAlias

from .._utils import PropertyInfo
from .data_content import DataContent
from .text_content import TextContent
from .tool_request_content import ToolRequestContent
from .tool_response_content import ToolResponseContent

__all__ = ["TaskMessageContent"]

TaskMessageContent: TypeAlias = Annotated[
    Union[TextContent, DataContent, ToolRequestContent, ToolResponseContent], PropertyInfo(discriminator="type")
]
