# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Optional
from typing_extensions import Literal, Required, TypeAlias, TypedDict

from ..data_content_param import DataContentParam
from ..text_content_param import TextContentParam
from ..tool_request_content_param import ToolRequestContentParam
from ..tool_response_content_param import ToolResponseContentParam

__all__ = [
    "NameRpcParams",
    "Params",
    "ParamsCreateTaskRequest",
    "ParamsCancelTaskRequest",
    "ParamsSendMessageRequest",
    "ParamsSendMessageRequestContent",
    "ParamsSendEventRequest",
    "ParamsSendEventRequestContent",
]


class NameRpcParams(TypedDict, total=False):
    method: Required[Literal["event/send", "task/create", "message/send", "task/cancel"]]

    params: Required[Params]

    id: Union[int, str, None]

    jsonrpc: Literal["2.0"]


class ParamsCreateTaskRequest(TypedDict, total=False):
    name: Optional[str]
    """The name of the task to create"""

    params: Optional[Dict[str, object]]
    """The parameters for the task"""


class ParamsCancelTaskRequest(TypedDict, total=False):
    task_id: Optional[str]
    """The ID of the task to cancel. Either this or task_name must be provided."""

    task_name: Optional[str]
    """The name of the task to cancel. Either this or task_id must be provided."""


ParamsSendMessageRequestContent: TypeAlias = Union[
    TextContentParam, DataContentParam, ToolRequestContentParam, ToolResponseContentParam
]


class ParamsSendMessageRequest(TypedDict, total=False):
    content: Required[ParamsSendMessageRequestContent]
    """The message that was sent to the agent"""

    stream: bool
    """Whether to stream the response message back to the client"""

    task_id: Optional[str]
    """The ID of the task that the message was sent to"""


ParamsSendEventRequestContent: TypeAlias = Union[
    TextContentParam, DataContentParam, ToolRequestContentParam, ToolResponseContentParam
]


class ParamsSendEventRequest(TypedDict, total=False):
    content: Optional[ParamsSendEventRequestContent]
    """The content to send to the event"""

    task_id: Optional[str]
    """The ID of the task that the event was sent to"""

    task_name: Optional[str]
    """The name of the task that the event was sent to"""


Params: TypeAlias = Union[
    ParamsCreateTaskRequest, ParamsCancelTaskRequest, ParamsSendMessageRequest, ParamsSendEventRequest
]
