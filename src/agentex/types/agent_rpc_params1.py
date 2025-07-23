# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from typing_extensions import Literal, Required, TypedDict

from . import agent_rpc_params

__all__ = ["AgentRpcParams"]


class AgentRpcParams(TypedDict, total=False):
    method: Required[Literal["event/send", "task/create", "message/send", "task/cancel"]]

    params: Required[agent_rpc_params.AgentRpcParams]
    """The parameters for the agent RPC request"""

    id: Union[int, str, None]

    jsonrpc: Literal["2.0"]
