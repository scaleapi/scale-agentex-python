# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from typing_extensions import Literal, Required, TypeAlias, TypedDict

from .send_event_request_param import SendEventRequestParam
from .cancel_task_request_param import CancelTaskRequestParam
from .create_task_request_param import CreateTaskRequestParam
from .send_message_request_param import SendMessageRequestParam

__all__ = ["AgentRpcParams", "Params"]


class AgentRpcParams(TypedDict, total=False):
    method: Required[Literal["event/send", "task/create", "message/send", "task/cancel"]]

    params: Required[Params]
    """The parameters for the agent RPC request"""

    id: Union[int, str, None]

    jsonrpc: Literal["2.0"]


Params: TypeAlias = Union[
    CreateTaskRequestParam, CancelTaskRequestParam, SendMessageRequestParam, SendEventRequestParam
]
