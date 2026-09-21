"""Wire-protocol shapes for Agentex.

The modules under `agentex.protocol.*` are the typed shapes for talking to
an Agentex agent over JSON-RPC (the ACP / Agent Communication Protocol)
without pulling in the heavy ADK runtime. They depend only on pydantic and
the Stainless-generated `agentex.types.*` surface, so they are safe to
import from a slim REST-only install.

Hand-rolled JSON-RPC clients (e.g. the one in `egp-api-backend`) can switch
from constructing `{"jsonrpc": "2.0", "method": "...", "params": {...}}`
dicts by hand to constructing `JSONRPCRequest(method=RPCMethod.TASK_CREATE,
params=CreateTaskParams(...).model_dump())`.

For back-compat, the same classes are re-exported from
`agentex.lib.types.{acp,json_rpc}` (the historical locations).
"""
