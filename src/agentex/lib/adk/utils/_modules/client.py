import threading
from typing import Dict, Optional, Any

from agentex import AsyncAgentex
from agentex.lib.environment_variables import EnvironmentVariables, refreshed_environment_variables

_client: Optional["AsyncAgentex"] = None
_cached_headers: Dict[str, str] = {}
_init_kwargs: Dict[str, Any] = {}
_lock = threading.RLock()


def _build_headers() -> Dict[str, str]:
    EnvironmentVariables.refresh()
    if refreshed_environment_variables and getattr(refreshed_environment_variables, "AGENT_ID", None):
        return {"x-agent-identity": refreshed_environment_variables.AGENT_ID}
    return {}


def get_async_agentex_client(**kwargs) -> "AsyncAgentex":
    """
    Return a cached AsyncAgentex instance (created synchronously).
    Each call re-checks env vars and updates client.default_headers if needed.
    """
    global _client, _cached_headers, _init_kwargs

    new_headers = _build_headers()

    with _lock:
        # First time (or kwargs changed) -> build a new client
        if _client is None or kwargs != _init_kwargs:
            _client = AsyncAgentex(default_headers=new_headers.copy(), **kwargs)
            _cached_headers = new_headers
            _init_kwargs = dict(kwargs)
            return _client

        # Same client; maybe headers changed
        if new_headers != _cached_headers:
            _cached_headers = new_headers
            _client.default_headers.clear()
            _client.default_headers.update(new_headers)

        return _client