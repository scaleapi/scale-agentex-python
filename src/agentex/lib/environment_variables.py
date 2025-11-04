
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv

from agentex.lib.utils.logging import make_logger
from agentex.lib.utils.model_utils import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]

logger = make_logger(__name__)


class EnvVarKeys(str, Enum):
    ENVIRONMENT = "ENVIRONMENT"
    TEMPORAL_ADDRESS = "TEMPORAL_ADDRESS"
    REDIS_URL = "REDIS_URL"
    AGENTEX_BASE_URL = "AGENTEX_BASE_URL"
    # Agent Identifiers
    AGENT_NAME = "AGENT_NAME"
    AGENT_DESCRIPTION = "AGENT_DESCRIPTION"
    AGENT_ID = "AGENT_ID"
    AGENT_API_KEY = "AGENT_API_KEY"
    # ACP Configuration
    ACP_URL = "ACP_URL"
    ACP_PORT = "ACP_PORT"
    ACP_TYPE = "ACP_TYPE"
    # Workflow Configuration
    WORKFLOW_NAME = "WORKFLOW_NAME"
    WORKFLOW_TASK_QUEUE = "WORKFLOW_TASK_QUEUE"
    # Temporal Worker Configuration
    HEALTH_CHECK_PORT = "HEALTH_CHECK_PORT"
    # Auth Configuration
    AUTH_PRINCIPAL_B64 = "AUTH_PRINCIPAL_B64"
    # Build Information
    BUILD_INFO_PATH = "BUILD_INFO_PATH"
    AGENT_INPUT_TYPE = "AGENT_INPUT_TYPE"


class Environment(str, Enum):
    LOCAL = "local"
    DEV = "development"
    STAGING = "staging"
    PROD = "production"


refreshed_environment_variables: EnvironmentVariables | None = None


class EnvironmentVariables(BaseModel):
    ENVIRONMENT: str = Environment.DEV
    TEMPORAL_ADDRESS: str | None = "localhost:7233"
    REDIS_URL: str | None = None
    AGENTEX_BASE_URL: str | None = "http://localhost:5003"
    # Agent Identifiers
    AGENT_NAME: str
    AGENT_DESCRIPTION: str | None = None
    AGENT_ID: str | None = None
    AGENT_API_KEY: str | None = None
    ACP_TYPE: str | None = "agentic"
    AGENT_INPUT_TYPE: str | None = None
    # ACP Configuration
    ACP_URL: str
    ACP_PORT: int = 8000
    # Workflow Configuration
    WORKFLOW_TASK_QUEUE: str | None = None
    WORKFLOW_NAME: str | None = None
    # Temporal Worker Configuration
    HEALTH_CHECK_PORT: int = 80
    # Auth Configuration
    AUTH_PRINCIPAL_B64: str | None = None
    # Build Information
    BUILD_INFO_PATH: str | None = None

    @classmethod
    def refresh(cls) -> EnvironmentVariables:
        global refreshed_environment_variables
        if refreshed_environment_variables is not None:
            return refreshed_environment_variables

        logger.info("Refreshing environment variables")
        if os.environ.get(EnvVarKeys.ENVIRONMENT) == Environment.DEV:
            # Load global .env file first
            global_env_path = PROJECT_ROOT / ".env"
            if global_env_path.exists():
                logger.debug(f"Loading global environment variables FROM: {global_env_path}")
                load_dotenv(dotenv_path=global_env_path, override=False)

            # Load local project .env.local file (takes precedence)
            local_env_path = Path.cwd().parent / ".env.local"
            if local_env_path.exists():
                logger.debug(f"Loading local environment variables FROM: {local_env_path}")
                load_dotenv(dotenv_path=local_env_path, override=True)

        # Create kwargs dict with environment variables, using None for missing values
        # Pydantic will use the default values when None is passed for optional fields
        kwargs = {}
        for key in EnvVarKeys:
            env_value = os.environ.get(key.value)
            if env_value is not None:
                kwargs[key.value] = env_value

        environment_variables = EnvironmentVariables(**kwargs)
        refreshed_environment_variables = environment_variables
        return refreshed_environment_variables
