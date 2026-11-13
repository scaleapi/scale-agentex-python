"""Pytest setup for this tutorial's tests.

``project.workflow`` reads environment variables when it is imported, so the offline tests need them set and
this tutorial's ``project`` package importable. Both are arranged here for this tutorial's tests only, and any
``project`` package already imported (another tutorial's, in a session that collects several) is cleared before
and after them.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator

import pytest

TUTORIAL_DIR = os.path.dirname(os.path.abspath(__file__))

# Values already set in the environment win.
ENV_DEFAULTS = {
    "AGENT_NAME": "at080-open-ai-agents-sdk-human-in-the-loop",
    "ACP_URL": "http://localhost:8000",
    "WORKFLOW_NAME": "at080-open-ai-agents-sdk-human-in-the-loop",
    # project.workflow refuses to import without an OpenAI key. The offline tests never call OpenAI, so a
    # placeholder is enough when no real key is set.
    "OPENAI_API_KEY": "offline-test-placeholder",
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
        _forget_project_modules()
        try:
            yield
        finally:
            _forget_project_modules()
