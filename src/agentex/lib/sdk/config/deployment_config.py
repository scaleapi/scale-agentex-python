"""Back-compat shim. The canonical location is :mod:`agentex.config.deployment_config`.

Kept here so existing ``from agentex.lib.sdk.config.deployment_config import ...``
imports continue to work. New code should import from the canonical path.
"""

from agentex.config.deployment_config import (  # noqa: F401
    ImageConfig,
    ClusterConfig,
    ResourceConfig,
    DeploymentConfig,
    AuthenticationConfig,
    ResourceRequirements,
    ImagePullSecretConfig,
    InjectedSecretsValues,
    GlobalDeploymentConfig,
    InjectedImagePullSecretValues,
)
