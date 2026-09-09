import os
from typing import override

import httpx

from agentex import AsyncAgentex
from agentex.lib.utils.logging import make_logger
from agentex.lib.environment_variables import EnvironmentVariables

logger = make_logger(__name__)


class EnvAuth(httpx.Auth):
    def __init__(self, header_name="x-agent-api-key"):
        self.header_name = header_name

    @override
    def auth_flow(self, request):
        # This gets called for every request
        env_vars = EnvironmentVariables.refresh()
        if env_vars:
            agent_api_key = env_vars.AGENT_API_KEY  
            if agent_api_key:
                request.headers[self.header_name] = agent_api_key
                masked_key = agent_api_key[-4:] if agent_api_key and len(agent_api_key) > 4 else "****"
                logger.info(f"Adding header {self.header_name}:{masked_key}")
        yield request


# HTTP timeouts for the AgentEx client, in seconds. Defaults match the SDK's
# DEFAULT_TIMEOUT, so leaving these unset changes nothing.
_TIMEOUT_ENV_DEFAULTS = {
    "connect": ("AGENTEX_CLIENT_CONNECT_TIMEOUT_SECONDS", 5.0),
    "read": ("AGENTEX_CLIENT_READ_TIMEOUT_SECONDS", 300.0),
    "write": ("AGENTEX_CLIENT_WRITE_TIMEOUT_SECONDS", 300.0),
    "pool": ("AGENTEX_CLIENT_POOL_TIMEOUT_SECONDS", 300.0),
}


def _timeout_from_env() -> httpx.Timeout:
    """Build the client timeout from environment variables.

    Read from ``os.environ`` rather than from ``EnvironmentVariables``. That model
    is loaded by worker startup and by ``EnvAuth.auth_flow`` on every request, and
    ``agentex.lib.adk.utils`` builds a client at import time, so a field added
    there would make a malformed timeout break all three. Reading here keeps the
    blast radius to the one value that is actually wrong.

    The connect timeout is the one worth raising: an AgentEx backend accepts
    connections serially, so connect latency grows with the number of callers and
    the 5s default is reached when a few hundred are in flight.
    """
    values = {}
    for field, (env_var, default) in _TIMEOUT_ENV_DEFAULTS.items():
        raw = os.environ.get(env_var)
        if raw is None or raw.strip() == "":
            values[field] = default
            continue
        try:
            values[field] = float(raw)
        except ValueError as exc:
            raise ValueError(f"{env_var} must be a number in seconds, got {raw!r}") from exc
    return httpx.Timeout(**values)


def create_async_agentex_client(**kwargs) -> AsyncAgentex:
    """Create an AsyncAgentex client.

    An explicit ``timeout=`` always wins; otherwise the timeout comes from the
    AGENTEX_CLIENT_*_TIMEOUT_SECONDS environment variables.
    """
    if "timeout" not in kwargs:
        kwargs["timeout"] = _timeout_from_env()
    client = AsyncAgentex(**kwargs)
    client._client.auth = EnvAuth()
    return client
