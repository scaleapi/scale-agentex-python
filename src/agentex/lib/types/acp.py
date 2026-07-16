"""Back-compat shim. The canonical location is :mod:`agentex.protocol.acp`.

Kept here so existing ``from agentex.lib.types.acp import ...`` imports
continue to work. New code should import from the canonical path.
"""

from agentex.protocol.acp import (  # noqa: F401
    RPC_SYNC_METHODS,
    PARAMS_MODEL_BY_METHOD,
    RPCMethod,
    SendEventParams,
    CancelTaskParams,
    CreateTaskParams,
    SendMessageParams,
    InterruptTaskParams,
)
