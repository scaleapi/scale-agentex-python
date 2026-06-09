"""Back-compat shim. The canonical location is :mod:`agentex.config.local_development_config`.

Kept here so existing ``from agentex.lib.sdk.config.local_development_config
import ...`` imports continue to work. New code should import from the canonical path.
"""

from agentex.config.local_development_config import (  # noqa: F401
    LocalAgentConfig,
    LocalPathsConfig,
    LocalDevelopmentConfig,
)
