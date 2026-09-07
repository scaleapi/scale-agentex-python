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


def _timeout_from_env() -> httpx.Timeout:
    """Build the client timeout from environment variables.

    Defaults match the SDK's DEFAULT_TIMEOUT, so an unconfigured process behaves
    exactly as before. The connect timeout is the one worth raising: an AgentEx
    backend accepts connections serially, so connect latency grows with the number
    of callers and the 5s default is reached when a few hundred are in flight.
    """
    env_vars = EnvironmentVariables.refresh()
    return httpx.Timeout(
        connect=env_vars.AGENTEX_CLIENT_CONNECT_TIMEOUT_SECONDS,
        read=env_vars.AGENTEX_CLIENT_READ_TIMEOUT_SECONDS,
        write=env_vars.AGENTEX_CLIENT_WRITE_TIMEOUT_SECONDS,
        pool=env_vars.AGENTEX_CLIENT_POOL_TIMEOUT_SECONDS,
    )


def create_async_agentex_client(**kwargs) -> AsyncAgentex:
    """Create an AsyncAgentex client.

    An explicit ``timeout=`` always wins; otherwise the timeout comes from the
    AGENTEX_CLIENT_*_TIMEOUT_SECONDS environment variables.
    """
    if "timeout" not in kwargs:
        try:
            kwargs["timeout"] = _timeout_from_env()
        except Exception as exc:
            # Never let timeout configuration stop a client being created.
            logger.warning("Falling back to SDK default timeout: %r", exc)
    client = AsyncAgentex(**kwargs)
    client._client.auth = EnvAuth()
    return client
