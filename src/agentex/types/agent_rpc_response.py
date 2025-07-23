# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Union, Optional
from typing_extensions import Literal

from .._models import BaseModel
from .agent_rpc_result import AgentRpcResult

__all__ = ["AgentRpcResponse"]


class AgentRpcResponse(BaseModel):
    result: Optional[AgentRpcResult] = None
    """The result of the agent RPC request"""

    id: Union[int, str, None] = None

    error: Optional[object] = None

    jsonrpc: Optional[Literal["2.0"]] = None
