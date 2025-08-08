import base64
import json
import os
import httpx
import asyncio

from agentex.lib.environment_variables import EnvironmentVariables, refreshed_environment_variables
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

def get_auth_principal(env_vars: EnvironmentVariables):
    if not env_vars.AUTH_PRINCIPAL_B64:
        return None

    try:
        decoded_str = base64.b64decode(env_vars.AUTH_PRINCIPAL_B64).decode('utf-8')
        return json.loads(decoded_str)
    except Exception:
        return None

async def register_agent(env_vars: EnvironmentVariables):
    """Register this agent with the Agentex server"""
    if not env_vars.AGENTEX_BASE_URL:
        logger.warning("AGENTEX_BASE_URL is not set, skipping registration")
        return
    # Build the agent's own URL
    full_acp_url = f"{env_vars.ACP_URL.rstrip('/')}:{env_vars.ACP_PORT}"

    description = (
        env_vars.AGENT_DESCRIPTION
        or f"Generic description for agent: {env_vars.AGENT_NAME}"
    )

    # Prepare registration data
    registration_data = {
        "name": env_vars.AGENT_NAME,
        "description": description,
        "acp_url": full_acp_url,
        "acp_type": env_vars.ACP_TYPE,
        "principal_context": get_auth_principal(env_vars)
    }

    if env_vars.AGENT_ID:
        registration_data["agent_id"] = env_vars.AGENT_ID

    # Make the registration request
    registration_url = f"{env_vars.AGENTEX_BASE_URL.rstrip('/')}/agents/register"
    # Retry logic with configurable attempts and delay
    max_retries = 3
    base_delay = 5  # seconds
    last_exception = None

    attempt = 0
    while attempt < max_retries:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    registration_url, json=registration_data, timeout=30.0
                )
                if response.status_code == 200:
                    agent = response.json()
                    agent_id, agent_name = agent["id"], agent["name"]
                    agent_api_key = agent["agent_api_key"]

                    os.environ["AGENT_ID"] = agent_id
                    os.environ["AGENT_NAME"] = agent_name
                    os.environ["AGENT_API_KEY"] = agent_api_key
                    env_vars.AGENT_ID = agent_id
                    env_vars.AGENT_NAME = agent_name
                    env_vars.AGENT_API_KEY = agent_api_key
                    global refreshed_environment_variables
                    refreshed_environment_variables = env_vars
                    logger.info(
                        f"Successfully registered agent '{env_vars.AGENT_NAME}' with Agentex server with acp_url: {full_acp_url}. Registration data: {registration_data}"
                    )
                    return  # Success, exit the retry loop
                else:
                    error_msg = f"Failed to register agent. Status: {response.status_code}, Response: {response.text}"
                    logger.error(error_msg)
                    last_exception = Exception(
                        f"Failed to startup agent: {response.text}"
                    )

        except Exception as e:
            logger.error(
                f"Exception during agent registration attempt {attempt + 1}: {e}"
            )
            last_exception = e
        attempt += 1
        if attempt < max_retries:
            delay = (attempt) * base_delay  # 5, 10, 15 seconds
            logger.info(
                f"Retrying in {delay} seconds... (attempt {attempt}/{max_retries})"
            )
            await asyncio.sleep(delay)

    # If we get here, all retries failed
    raise last_exception or Exception(
        f"Failed to register agent after {max_retries} attempts"
    )
