"""Back-compat shim. The canonical location is :mod:`agentex.config.agent_configs`.

Kept here so existing ``from agentex.lib.types.agent_configs import ...`` imports
continue to work. New code should import from the canonical path.
"""

from agentex.config.agent_configs import (  # noqa: F401
    TemporalConfig,
    TemporalWorkerConfig,
    TemporalWorkflowConfig,
)
