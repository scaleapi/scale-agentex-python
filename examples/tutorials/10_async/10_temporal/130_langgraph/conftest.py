"""Pytest setup for this tutorial's tests.

``project.workflow`` reads environment variables when it is imported, so the offline tests need them set and
this tutorial's ``project`` package importable. Both are arranged here for this tutorial's tests only. Any
``project`` package already imported (another tutorial's, in a session that collects several) is cleared before
and after them, and so is the SDK's cached ``EnvironmentVariables``, so this tutorial's workflow reads its own
values.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator

import pytest

TUTORIAL_DIR = os.path.dirname(os.path.abspath(__file__))

# Values already set in the environment win.
ENV_DEFAULTS = {
    "AGENT_NAME": "at130-langgraph",
    "ACP_URL": "http://localhost:8000",
    "WORKFLOW_NAME": "at130-langgraph",
}


def _forget_project_modules() -> None:
    for name in [name for name in sys.modules if name == "project" or name.startswith("project.")]:
        del sys.modules[name]


@pytest.fixture(autouse=True, scope="module")
def _tutorial_environment() -> Iterator[None]:
    with pytest.MonkeyPatch.context() as patch:
        for name, value in ENV_DEFAULTS.items():
            if not os.environ.get(name):
                patch.setenv(name, value)
        patch.syspath_prepend(TUTORIAL_DIR)
        # EnvironmentVariables.refresh() keeps the first values it reads for the whole process.
        patch.setattr("agentex.lib.environment_variables.refreshed_environment_variables", None)
        _forget_project_modules()
        try:
            yield
        finally:
            _forget_project_modules()
