"""Conformance-suite test setup.

Eagerly import every per-harness conformance module so each one's module-level
``register(...)`` calls run before any test executes. This makes
``all_fixtures()`` complete and independent of pytest's collection/import order
(the runner documents that cross-module registration order is not guaranteed),
so the cross-harness ``test_span_derivation_is_deterministic`` guard in
``test_conformance.py`` covers the full fixture set even when this directory is
run in isolation.
"""

from __future__ import annotations

# Importing these for their registration side effects only.
from . import (
    test_codex_conformance,  # noqa: F401
    test_openai_conformance,  # noqa: F401
    test_langgraph_conformance,  # noqa: F401
    test_claude_code_conformance,  # noqa: F401
    test_pydantic_ai_conformance,  # noqa: F401
)
