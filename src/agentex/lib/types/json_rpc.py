"""Back-compat shim. The canonical location is :mod:`agentex.protocol.json_rpc`.

Kept here so existing ``from agentex.lib.types.json_rpc import ...`` imports
continue to work. New code should import from the canonical path.
"""

from agentex.protocol.json_rpc import (  # noqa: F401
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
)
