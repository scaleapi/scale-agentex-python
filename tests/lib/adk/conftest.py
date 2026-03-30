"""Conftest for ADK tests.

Mocks optional dependencies that are imported as side effects of the ADK
package init but are not needed for unit tests.
"""

import sys
from unittest.mock import MagicMock

# Mock all langchain_core and langgraph submodules used by the ADK package.
# These are imported as side effects of agentex.lib.adk.__init__ but are not
# needed for task-related unit tests.

_langchain_core_modules = [
    "langchain_core",
    "langchain_core.runnables",
    "langchain_core.runnables.config",
    "langchain_core.outputs",
    "langchain_core.messages",
    "langchain_core.callbacks",
]

_langgraph_modules = [
    "langgraph",
    "langgraph.checkpoint",
    "langgraph.checkpoint.base",
    "langgraph.checkpoint.serde",
    "langgraph.checkpoint.serde.types",
]

for mod_name in _langchain_core_modules + _langgraph_modules:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()
