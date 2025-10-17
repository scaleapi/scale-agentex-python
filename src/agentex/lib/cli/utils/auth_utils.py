from __future__ import annotations

import json
import base64
from typing import Any, Dict

from agentex.lib.sdk.config.agent_manifest import AgentManifest
from agentex.lib.sdk.config.environment_config import AgentAuthConfig


# DEPRECATED: Old function for backward compatibility
# Will be removed in future version
def _encode_principal_context(manifest: AgentManifest) -> str | None:  # noqa: ARG001
    """
    DEPRECATED: This function is deprecated as AgentManifest no longer contains auth.
    Use _encode_principal_context_from_env_config instead.
    
    This function is kept temporarily for backward compatibility during migration.
    """
    # AgentManifest no longer has auth field - this will always return None
    return None


def _encode_principal_context_from_env_config(auth_config: "AgentAuthConfig | None") -> str | None:
    """
    Encode principal context from environment configuration.
    
    Args:
        auth_config: AgentAuthConfig containing principal configuration
        
    Returns:
        Base64-encoded JSON string of the principal, or None if no principal
    """
    if auth_config is None:
        return None
    
    principal = auth_config.principal
    if not principal:
        return None

    json_str = json.dumps(principal, separators=(',', ':'))
    encoded_bytes = base64.b64encode(json_str.encode('utf-8'))
    return encoded_bytes.decode('utf-8')


def _encode_principal_dict(principal: Dict[str, Any]) -> str | None:
    """
    Encode principal dictionary directly.
    
    Args:
        principal: Dictionary containing principal configuration
        
    Returns:
        Base64-encoded JSON string of the principal, or None if principal is empty
    """
    if not principal:
        return None

    json_str = json.dumps(principal, separators=(',', ':'))
    encoded_bytes = base64.b64encode(json_str.encode('utf-8'))
    return encoded_bytes.decode('utf-8')
