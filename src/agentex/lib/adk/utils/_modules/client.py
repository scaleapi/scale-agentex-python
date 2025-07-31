import httpx

from agentex import AsyncAgentex
from agentex.lib.environment_variables import refreshed_environment_variables
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class EnvAuth(httpx.Auth):
    def __init__(self, header_name="x-agent-identity"):
        self.header_name = header_name

    def auth_flow(self, request):
        # This gets called for every request

        agent_id = refreshed_environment_variables.AGENT_ID
        if agent_id:
            request.headers[self.header_name] = agent_id
            logger.info(f"Adding header {self.header_name}:{agent_id}")
        yield request


def create_async_agentex_client(**kwargs) -> AsyncAgentex:
    http_client = httpx.AsyncClient(auth=EnvAuth())

    return AsyncAgentex(http_client=http_client, **kwargs)
