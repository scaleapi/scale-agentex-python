"""Back-compat shim. The canonical location is :mod:`agentex.config.agent_config`.

Kept here so existing ``from agentex.lib.sdk.config.agent_config import ...``
imports continue to work. New code should import from the canonical path.
"""

from agentex.config.agent_config import AgentConfig  # noqa: F401
