"""
Configuration for AgentEx Testing Framework.

Centralized configuration management with environment variable support.
"""

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TestConfig:
    """Configuration for AgentEx behavior testing."""

    # Infrastructure
    base_url: str
    health_check_timeout: float

    # Polling configuration
    initial_poll_interval: float
    max_poll_interval: float
    poll_backoff_factor: float

    # Retry configuration
    api_retry_attempts: int
    api_retry_delay: float
    api_retry_backoff_factor: float

    # Task management
    task_name_prefix: str


def load_config() -> TestConfig:
    """
    Load test configuration from environment variables.

    Environment Variables:
        AGENTEX_BASE_URL: AgentEx server URL (default: http://localhost:5003)
        AGENTEX_HEALTH_TIMEOUT: Health check timeout in seconds (default: 5.0)
        AGENTEX_POLL_INTERVAL: Initial poll interval in seconds (default: 1.0)
        AGENTEX_MAX_POLL_INTERVAL: Maximum poll interval in seconds (default: 8.0)
        AGENTEX_POLL_BACKOFF: Poll backoff multiplier (default: 2.0)
        AGENTEX_API_RETRY_ATTEMPTS: Number of retry attempts for API calls (default: 3)
        AGENTEX_API_RETRY_DELAY: Initial retry delay in seconds (default: 0.5)
        AGENTEX_API_RETRY_BACKOFF: Retry backoff multiplier (default: 2.0)
        AGENTEX_TEST_PREFIX: Prefix for test task names (default: "test")

    Returns:
        TestConfig instance with loaded values
    """
    return TestConfig(
        # Infrastructure
        base_url=os.getenv("AGENTEX_BASE_URL", "http://localhost:5003"),
        health_check_timeout=float(os.getenv("AGENTEX_HEALTH_TIMEOUT", "5.0")),
        # Polling
        initial_poll_interval=float(os.getenv("AGENTEX_POLL_INTERVAL", "1.0")),
        max_poll_interval=float(os.getenv("AGENTEX_MAX_POLL_INTERVAL", "8.0")),
        poll_backoff_factor=float(os.getenv("AGENTEX_POLL_BACKOFF", "2.0")),
        # Retry
        api_retry_attempts=int(os.getenv("AGENTEX_API_RETRY_ATTEMPTS", "3")),
        api_retry_delay=float(os.getenv("AGENTEX_API_RETRY_DELAY", "0.5")),
        api_retry_backoff_factor=float(os.getenv("AGENTEX_API_RETRY_BACKOFF", "2.0")),
        # Task management
        task_name_prefix=os.getenv("AGENTEX_TEST_PREFIX", "test"),
    )


# Global config instance
config = load_config()


def is_agentex_available() -> bool:
    """
    Check if AgentEx infrastructure is available.

    Returns:
        True if AgentEx is healthy, False otherwise
    """
    try:
        import httpx

        response = httpx.get(f"{config.base_url}/healthz", timeout=config.health_check_timeout)
        is_healthy = response.status_code == 200

        if not is_healthy:
            logger.warning(f"AgentEx health check failed: status={response.status_code}, url={config.base_url}/healthz")

        return is_healthy
    except Exception as e:
        logger.warning(f"AgentEx health check failed: {e}")
        return False
