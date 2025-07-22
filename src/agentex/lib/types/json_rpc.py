from typing import Any, Literal

from agentex.lib.utils.model_utils import BaseModel


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 Error

    Attributes:
        code: The error code
        message: The error message
        data: The error data
    """

    code: int
    message: str
    data: Any | None = None


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 Request

    Attributes:
        jsonrpc: The JSON-RPC version
        method: The method to call
        params: The parameters for the request
        id: The ID of the request
    """

    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: dict[str, Any]
    id: int | str | None = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 Response

    Attributes:
        jsonrpc: The JSON-RPC version
        result: The result of the request
        error: The error of the request
        id: The ID of the request
    """

    jsonrpc: Literal["2.0"] = "2.0"
    result: dict[str, Any] | None = None
    error: JSONRPCError | None = None
    id: int | str | None = None
