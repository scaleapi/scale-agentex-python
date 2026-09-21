"""Back-compat shim. The canonical location is :mod:`agentex.config.build_config`.

Kept here so existing ``from agentex.lib.sdk.config.build_config import ...``
imports continue to work. New code should import from the canonical path.
"""

from agentex.config.build_config import (  # noqa: F401
    BuildConfig,
    BuildContext,
)
