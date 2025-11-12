"""
Validation framework for agent configuration files.

This module provides validation functions for agent configurations,
with clear error messages and best practices enforcement.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path

from agentex.lib.utils.logging import make_logger
from agentex.lib.sdk.config.environment_config import AgentEnvironmentConfig, AgentEnvironmentsConfig

logger = make_logger(__name__)


class ConfigValidationError(Exception):
    """Exception raised when configuration validation fails."""
    
    def __init__(self, message: str, file_path: Optional[str] = None):
        self.file_path = file_path
        super().__init__(message)


class EnvironmentsValidationError(ConfigValidationError):
    """Exception raised when environments.yaml validation fails."""
    pass


def validate_environments_config(
    environments_config: AgentEnvironmentsConfig, 
    required_environments: Optional[List[str]] = None
) -> None:
    """
    Validate environments configuration with comprehensive checks.
    
    Args:
        environments_config: The loaded environments configuration
        required_environments: List of environment names that must be present
        
    Raises:
        EnvironmentsValidationError: If validation fails
    """
    # Check for required environments
    if required_environments:
        missing_envs: List[str] = []
        for env_name in required_environments:
            if env_name not in environments_config.environments:
                missing_envs.append(env_name)
        
        if missing_envs:
            available_envs = list(environments_config.environments.keys())
            raise EnvironmentsValidationError(
                f"Missing required environments: {', '.join(missing_envs)}. "
                f"Available environments: {', '.join(available_envs)}"
            )
    
    # Validate each environment configuration
    for env_name, env_config in environments_config.environments.items():
        try:
            _validate_single_environment_config(env_name, env_config)
        except Exception as e:
            raise EnvironmentsValidationError(
                f"Environment '{env_name}' configuration error: {str(e)}"
            ) from e


def _validate_single_environment_config(env_name: str, env_config: AgentEnvironmentConfig) -> None:
    """
    Validate a single environment configuration.
    
    Args:
        env_name: Name of the environment
        env_config: AgentEnvironmentConfig instance
        
    Raises:
        ValueError: If validation fails
    """
    # Validate namespace naming conventions if kubernetes config exists
    if env_config.kubernetes and env_config.kubernetes.namespace:
        namespace = env_config.kubernetes.namespace
        
        # Check for common namespace naming issues
        if namespace != namespace.lower():
            logger.warning(
                f"Namespace '{namespace}' contains uppercase letters. "
                "Kubernetes namespaces should be lowercase."
            )
        
        if namespace.startswith('-') or namespace.endswith('-'):
            raise ValueError(
                f"Namespace '{namespace}' cannot start or end with hyphens"
            )
    
    # Validate auth principal
    principal = env_config.auth.principal
    if not principal.get('user_id'):
        raise ValueError("Auth principal must contain non-empty 'user_id'")
    
    # Check for environment-specific user_id patterns
    user_id = principal['user_id']
    if isinstance(user_id, str):
        if not any(env_name.lower() in user_id.lower() for env_name in ['dev', 'prod', 'staging', env_name]):
            logger.warning(
                f"User ID '{user_id}' doesn't contain environment indicator. "
                f"Consider including '{env_name}' in the user_id for clarity."
            )
    
    # Validate helm overrides if present
    if env_config.helm_overrides:
        _validate_helm_overrides(env_config.helm_overrides)


def _validate_helm_overrides(helm_overrides: Dict[str, Any]) -> None:
    """
    Validate helm override configuration.
    
    Args:
        helm_overrides: Dictionary of helm overrides
        
    Raises:
        ValueError: If validation fails
    """
    # Check for common helm override issues
    if 'resources' in helm_overrides:
        resources = helm_overrides['resources']
        if isinstance(resources, dict):
            # Validate resource format
            if 'requests' in resources or 'limits' in resources:
                for resource_type in ['requests', 'limits']:
                    if resource_type in resources:
                        resource_config: Any = resources[resource_type]
                        if isinstance(resource_config, dict):
                            # Check for valid resource specifications
                            for key, value in resource_config.items():
                                if key in ['cpu', 'memory'] and not isinstance(value, str):
                                    logger.warning(
                                        f"Resource {key} should be a string (e.g., '500m', '1Gi'), "
                                        f"got {type(value).__name__}: {value}"
                                    )


def validate_environments_yaml_file(file_path: str) -> AgentEnvironmentsConfig:
    """
    Load and validate environments.yaml file.
    
    Args:
        file_path: Path to environments.yaml file
        
    Returns:
        Validated AgentEnvironmentsConfig
        
    Raises:
        EnvironmentsValidationError: If file is invalid
    """
    try:
        environments_config = AgentEnvironmentsConfig.from_yaml(file_path)
        validate_environments_config(environments_config)
        return environments_config
    except FileNotFoundError:
        raise EnvironmentsValidationError(
            f"environments.yaml not found: {file_path}\n\n"
            "📋 Why required:\n"
            "   Environment-specific settings (auth, namespace, resources)\n"
            "   must be separated from global manifest for proper isolation.",
            file_path=file_path
        ) from None
    except Exception as e:
        raise EnvironmentsValidationError(
            f"Invalid environments.yaml file: {str(e)}",
            file_path=file_path
        ) from e


def validate_manifest_and_environments(
    manifest_path: str, 
    required_environment: Optional[str] = None
) -> tuple[str, AgentEnvironmentsConfig]:
    """
    Validate both manifest.yaml and environments.yaml files together.
    
    Args:
        manifest_path: Path to manifest.yaml file
        required_environment: Specific environment that must be present
        
    Returns:
        Tuple of (manifest_path, environments_config)
        
    Raises:
        ConfigValidationError: If validation fails
    """
    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        raise ConfigValidationError(f"Manifest file not found: {manifest_path}")
    
    # Look for environments.yaml in same directory
    environments_file = manifest_file.parent / "environments.yaml"
    environments_config = validate_environments_yaml_file(str(environments_file))
    
    # Validate specific environment if requested
    if required_environment:
        validate_environments_config(
            environments_config, 
            required_environments=[required_environment]
        )
    
    return manifest_path, environments_config


def generate_helpful_error_message(error: Exception, context: str = "") -> str:
    """
    Generate helpful error message with troubleshooting tips.
    
    Args:
        error: The original exception
        context: Additional context about where the error occurred
        
    Returns:
        Formatted error message with troubleshooting tips
    """
    base_msg = str(error)
    
    if context:
        base_msg = f"{context}: {base_msg}"
    
    # Add troubleshooting tips based on error type
    if isinstance(error, FileNotFoundError):
        if "environments.yaml" in base_msg:
            base_msg += (
                "\n\n🔧 Troubleshooting:\n"
                "1. Check file location: should be next to manifest.yaml\n"
                "2. Verify file permissions"
            )
    elif "user_id" in base_msg.lower():
        base_msg += (
            "\n\n💡 Auth Principal Tips:\n"
            "- user_id should be unique per environment\n"
            "- Include environment name (e.g., 'dev_my_agent')\n"
            "- Use consistent naming convention across agents"
        )
    elif "namespace" in base_msg.lower():
        base_msg += (
            "\n\n🏷️  Namespace Tips:\n"
            "- Use lowercase letters, numbers, and hyphens only\n"
            "- Include team and environment (e.g., 'team-dev-agent')\n"
            "- Keep under 63 characters"
        )
    
    return base_msg
