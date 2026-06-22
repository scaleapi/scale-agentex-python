"""Back-compat shim and yaml loaders for environment configuration.

The model classes' canonical location is
:mod:`agentex.config.environment_config`; they are re-exported here so existing
``from agentex.lib.sdk.config.environment_config import ...`` imports keep
working. The yaml-loading helpers stay here (CLI/build-side) so the promoted
models remain slim-safe.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from agentex.config.environment_config import (  # noqa: F401
    AgentAuthConfig,
    OciRegistryConfig,
    AgentKubernetesConfig,
    AgentEnvironmentConfig,
    AgentEnvironmentsConfig,
)


def load_environments_config(file_path: str) -> AgentEnvironmentsConfig:
    """Load and validate an environments.yaml into an AgentEnvironmentsConfig.

    Args:
        file_path: Path to environments.yaml file

    Returns:
        Parsed and validated AgentEnvironmentsConfig

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is invalid or doesn't validate
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"environments.yaml not found: {file_path}")

    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError("environments.yaml file is empty")

        return AgentEnvironmentsConfig.model_validate(data)

    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format in {file_path}: {e}") from e
    except Exception as e:
        raise ValueError(f"Failed to load environments.yaml from {file_path}: {e}") from e


def load_environments_config_from_manifest_dir(manifest_dir: Path) -> AgentEnvironmentsConfig | None:
    """Helper function to load environments.yaml from same directory as manifest.yaml.

    Args:
        manifest_dir: Directory containing manifest.yaml

    Returns:
        AgentEnvironmentsConfig if environments.yaml exists, None otherwise

    Raises:
        ValueError: If environments.yaml exists but is invalid
    """
    environments_file = manifest_dir / "environments.yaml"
    if not environments_file.exists():
        return None

    return load_environments_config(str(environments_file))
