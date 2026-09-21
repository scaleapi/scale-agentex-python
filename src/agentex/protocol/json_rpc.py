from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

# Preserve the config the previous `agentex.lib.utils.model_utils.BaseModel`
# applied — `from_attributes=True` lets callers `model_validate` from
# attribute-bearing objects (not just dicts); `populate_by_name=True` is a
# harmless default future-proofing for any field aliases.
_PROTOCOL_MODEL_CONFIG = ConfigDict(from_attributes=True, populate_by_name=True)


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 Error

    Attributes:
        code: The error code
        message: The error message
        data: The error data
    """

    model_config = _PROTOCOL_MODEL_CONFIG

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

    model_config = _PROTOCOL_MODEL_CONFIG

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

    model_config = _PROTOCOL_MODEL_CONFIG

    jsonrpc: Literal["2.0"] = "2.0"
    result: dict[str, Any] | None = None
    error: JSONRPCError | None = None
    id: int | str | None = None
