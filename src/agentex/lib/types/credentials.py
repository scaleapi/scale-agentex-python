"""Back-compat shim. The canonical location is :mod:`agentex.config.credentials`.

Kept here so existing ``from agentex.lib.types.credentials import ...`` imports
continue to work. New code should import from the canonical path.
"""

from agentex.config.credentials import CredentialMapping  # noqa: F401
