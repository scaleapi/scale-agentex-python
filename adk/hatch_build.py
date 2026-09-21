"""Builds the agentex/lib force-include map per-file so test files can be pruned
— force-include ignores `exclude` (hatchling #1395)."""

from __future__ import annotations

import os

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_SKIP_DIRS = {"__pycache__", "tests"}
_SKIP_NAMES = {"conftest.py", "pytest.ini", "run_tests.py"}
# Floor below the ~333 shippable files: a collapse means the walk broke — fail
# loud rather than ship a near-empty wheel.
_MIN_FILES = 320


def _is_test_file(name: str) -> bool:
    return name in _SKIP_NAMES or (name.startswith("test_") and name.endswith(".py"))


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict) -> None:  # noqa: ARG002
        lib_root = os.path.normpath(os.path.join(self.root, "..", "src", "agentex", "lib"))
        force_include = build_data.setdefault("force_include", {})
        collected = 0
        for dirpath, dirnames, filenames in os.walk(lib_root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for name in filenames:
                if _is_test_file(name):
                    continue
                src = os.path.join(dirpath, name)
                rel = os.path.relpath(src, lib_root)
                force_include[src] = os.path.join("agentex", "lib", rel)
                collected += 1
        if collected < _MIN_FILES:
            raise RuntimeError(
                f"agentex/lib force-include collected only {collected} files "
                f"(expected >= {_MIN_FILES}); aborting build."
            )
