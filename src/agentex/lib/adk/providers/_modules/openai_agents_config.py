"""
OpenAI Agents SDK Client Configuration

Configures custom OpenAI clients specifically for the OpenAI Agents SDK.
This affects ONLY the OpenAI Agents SDK integration (Agent and Runner).

For LiteLLM integration, use separate LiteLLM configuration methods.
"""

from typing import Union
from openai import AsyncOpenAI, AsyncAzureOpenAI
from agents import set_default_openai_client
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

# Type alias for supported async OpenAI clients
AsyncOpenAIClient = Union[AsyncOpenAI, AsyncAzureOpenAI]

_client_initialized = False


def initialize_openai_agents_client(client: AsyncOpenAIClient) -> None:
    """
    Initialize custom OpenAI client for OpenAI Agents SDK operations.

    ⚠️ IMPORTANT: This ONLY affects the OpenAI Agents SDK integration
    (Agent and Runner classes). It does NOT affect:
    - LiteLLM integration (use LiteLLM configuration separately)
    - SGP integration
    - Direct OpenAI API calls

    This should be called ONCE at application or worker startup, before any
    agents are created using the OpenAI Agents SDK.

    Args:
        client: Pre-configured async OpenAI client (AsyncOpenAI or AsyncAzureOpenAI)

    Raises:
        TypeError: If a non-async client is passed (will be caught by type checker)

    Examples:
        # Custom endpoint (e.g., LiteLLM proxy for cost tracking):
        from openai import AsyncOpenAI
        from agentex.lib.adk.providers._modules.openai_agents_config import (
            initialize_openai_agents_client
        )

        client = AsyncOpenAI(
            base_url="https://your-proxy.com/v1",
            api_key=os.getenv("CUSTOM_API_KEY")
        )
        initialize_openai_agents_client(client)

        # Azure OpenAI:
        from openai import AsyncAzureOpenAI

        client = AsyncAzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version="2024-02-01"
        )
        initialize_openai_agents_client(client)

        # For Temporal workers, call this in worker startup:
        # run_worker.py:
        #   initialize_openai_agents_client(client)
        #   # Then start worker...

    Note:
        If not called, the OpenAI Agents SDK uses default OpenAI configuration
        via the OPENAI_API_KEY environment variable.
    """
    global _client_initialized

    if _client_initialized:
        logger.warning(
            "OpenAI Agents SDK client already initialized. "
            "Ignoring subsequent initialization. "
            "This may indicate multiple workers or initialization calls."
        )
        return

    # Runtime validation for async client
    if not isinstance(client, (AsyncOpenAI, AsyncAzureOpenAI)):
        raise TypeError(
            f"Client must be AsyncOpenAI or AsyncAzureOpenAI, got {type(client).__name__}. "
            f"The OpenAI Agents SDK requires async clients. "
            f"Use AsyncOpenAI instead of OpenAI."
        )

    set_default_openai_client(client)
    logger.info(f"OpenAI Agents SDK client configured: {type(client).__name__}")

    _client_initialized = True


def is_openai_agents_client_initialized() -> bool:
    """
    Check if custom OpenAI Agents SDK client has been initialized.

    Returns:
        bool: True if initialize_openai_agents_client() has been called
    """
    return _client_initialized


def reset_openai_agents_client_initialization() -> None:
    """
    Reset initialization flag (primarily for testing).

    Warning: This does NOT reset the actual client in the agents library,
    only the initialization tracking flag in this module.
    """
    global _client_initialized
    _client_initialized = False
