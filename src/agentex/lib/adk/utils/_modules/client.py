import os

from agentex import AsyncAgentex
from agentex.lib.environment_variables import refreshed_environment_variables


def create_async_agentex_client(**kwargs):
    #agent_id = refreshed_environment_variables.AGENT_ID
    default_headers = {
        "x-agent-identity": os.environ["AGENT_API_KEY"]
    }
    return AsyncAgentex(default_headers=default_headers, **kwargs)
