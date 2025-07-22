from typing import Any
from mcp import StdioServerParameters


def redact_mcp_server_params(
    mcp_server_params: list[StdioServerParameters],
) -> list[dict[str, Any]]:
    """Redact MCP server params for logging."""
    return [
        {
            **{k: v for k, v in server_param.model_dump().items() if k != "env"},
            "env": dict.fromkeys(server_param.env, "********")
            if server_param.env
            else None,
        }
        for server_param in mcp_server_params
    ]
