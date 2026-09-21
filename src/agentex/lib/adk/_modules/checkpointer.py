from __future__ import annotations

from agentex.lib.adk.utils._modules.client import create_async_agentex_client
from agentex.lib.adk._modules._http_checkpointer import HttpCheckpointSaver


async def create_checkpointer() -> HttpCheckpointSaver:
    """Create an HTTP-proxy checkpointer for LangGraph.

    Checkpoint operations are proxied through the agentex backend API.
    No direct database connection needed — auth is handled via the
    agent API key (injected automatically by agentex).

    Usage:
        checkpointer = await create_checkpointer()
        graph = builder.compile(checkpointer=checkpointer)
    """
    client = create_async_agentex_client()
    return HttpCheckpointSaver(client=client)
