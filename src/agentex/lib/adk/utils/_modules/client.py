import httpx

from agentex import AsyncAgentex
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class EnvAuth(httpx.Auth):
    def __init__(self, header_name="x-agent-api-key"):
        self.header_name = header_name

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


def create_async_agentex_client(**kwargs) -> AsyncAgentex:
    client = AsyncAgentex(**kwargs)
    client._client.auth = EnvAuth()
    return client
