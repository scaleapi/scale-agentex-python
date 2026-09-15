"""Tests for handing agentex's loggers over to a root logging pipeline.

``make_logger`` attaches a handler to each module's OWN (leaf) logger. sgp-obs' logs
pipeline replaces the handlers on the ROOT logger and deliberately leaves named loggers
alone, on the grounds that a named logger's handler may be there on purpose. Each is
defensible; together they print every record twice — once in agentex's plain text from
the leaf, once as pipeline JSON from root. Measured on sgp-obs 0.16.0: one
``logger.info()`` produced two stdout lines and sgp-obs named 63 loggers as "bypassing
log governance".

The duplicate is not merely redundant. It is emitted before the pipeline's filters, so
it carries no ``agent_id``/``task_id``, is not governed by the allowlist, and is not
truncated.

The fix has two halves and needs both, which is what the subprocess tests pin:

* the sweep clears loggers that ALREADY exist when it runs;
* the latch stops ``make_logger`` attaching to loggers created AFTERWARDS.

A sweep alone misses the second: agentex imports several harness modules lazily, so
their ``make_logger`` runs later and would attach a fresh duplicate.
"""

from __future__ import annotations

import os
import sys
import logging
import textwrap
import subprocess
from typing import override
from pathlib import Path

import pytest

from agentex.lib.utils import logging as agentex_logging
from agentex.lib.utils.logging import make_logger, route_agentex_loggers_to_root

_SRC = Path(__file__).resolve().parents[4]


@pytest.fixture(autouse=True)
def _restore_logging():
    """The latch and the loggers are process-wide; put both back."""
    saved = {
        name: (obj.handlers[:], obj.propagate)
        for name, obj in logging.Logger.manager.loggerDict.items()
        if isinstance(obj, logging.Logger)
    }
    try:
        yield
    finally:
        agentex_logging._reset_for_tests()
        for name, (handlers, propagate) in saved.items():
            existing = logging.Logger.manager.loggerDict.get(name)
            if isinstance(existing, logging.Logger):
                existing.handlers[:] = handlers
                existing.propagate = propagate


def _run(handover: bool) -> str:
    """One trial in its own process — root-logger state is global and cannot be
    isolated within a test session. Returns stdout+stderr."""
    program = textwrap.dedent(
        f"""
        import logging, sys
        from agentex.lib.utils.logging import make_logger, route_agentex_loggers_to_root

        # Exists BEFORE the handover, like any eagerly-imported agentex module.
        before = make_logger("agentex.lib.probe.before")

        # Stand in for sgp-obs' pipeline: a single handler on ROOT.
        root = logging.getLogger()
        root.handlers[:] = [logging.StreamHandler(sys.stdout)]
        root.setLevel(logging.INFO)

        if {handover!r}:
            route_agentex_loggers_to_root()

        # Created AFTER, like one of the lazily-imported harness modules.
        after = make_logger("agentex.lib.probe.after")

        before.info("MARKER-BEFORE")
        after.info("MARKER-AFTER")
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONPATH": str(_SRC), "LOG_LEVEL": "INFO", "ENVIRONMENT": "production"},
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return proc.stdout + proc.stderr


class TestEveryRecordIsPrintedOnce:
    def test_without_the_handover_everything_doubles(self):
        """The bug, pinned. If this ever reads 1, the other two tests below have
        stopped proving anything."""
        out = _run(handover=False)
        assert out.count("MARKER-BEFORE") == 2
        assert out.count("MARKER-AFTER") == 2

    def test_a_logger_created_before_the_handover_prints_once(self):
        out = _run(handover=True)
        assert out.count("MARKER-BEFORE") == 1

    def test_a_logger_created_after_the_handover_prints_once(self):
        """The half a sweep cannot reach: agentex imports harness modules lazily, so
        their make_logger runs after init and would attach a fresh duplicate."""
        out = _run(handover=True)
        assert out.count("MARKER-AFTER") == 1


class TestTheSweepIsNarrow:
    def test_it_clears_an_agentex_logger_that_has_a_handler(self):
        lg = logging.getLogger("agentex.lib.probe.sweep")
        lg.addHandler(logging.NullHandler())
        assert route_agentex_loggers_to_root() >= 1
        assert lg.handlers == []

    def test_it_leaves_other_packages_alone(self):
        """A third party's handler may be deliberate — which is exactly why sgp-obs
        warns about them rather than stripping them."""
        other = logging.getLogger("litellm.probe")
        handler = logging.NullHandler()
        other.addHandler(handler)
        route_agentex_loggers_to_root()
        assert other.handlers == [handler]

    def test_it_leaves_a_non_propagating_agentex_logger_alone(self):
        """Cut off from root on purpose, so nothing of its reaches the pipeline.
        Clearing its handlers would send its records NOWHERE — worse than a duplicate."""
        lg = logging.getLogger("agentex.lib.probe.isolated")
        handler = logging.NullHandler()
        lg.addHandler(handler)
        lg.propagate = False
        route_agentex_loggers_to_root()
        assert lg.handlers == [handler]

    def test_a_prefix_lookalike_is_not_swept(self):
        """`agentexfoo` is a different package, not a child of `agentex`."""
        lg = logging.getLogger("agentexfoo.probe")
        handler = logging.NullHandler()
        lg.addHandler(handler)
        route_agentex_loggers_to_root()
        assert lg.handlers == [handler]

    def test_handlers_are_flushed_before_removal(self):
        """A buffering handler would otherwise lose whatever it was holding."""
        flushed = []

        class Recording(logging.NullHandler):
            @override
            def flush(self):
                flushed.append(True)

        lg = logging.getLogger("agentex.lib.probe.flush")
        lg.addHandler(Recording())
        route_agentex_loggers_to_root()
        assert flushed == [True]


class TestMakeLoggerRespectsTheLatch:
    def test_it_attaches_nothing_once_the_pipeline_owns_logging(self):
        route_agentex_loggers_to_root()
        assert make_logger("agentex.lib.probe.after_latch").handlers == []

    def test_it_still_attaches_when_nothing_owns_logging(self):
        """The non-negotiable half: an agent without sgp-obs must log exactly as it
        did before any of this existed."""
        agentex_logging._reset_for_tests()
        assert make_logger("agentex.lib.probe.no_latch").handlers != []

    def test_the_level_is_applied_either_way(self, monkeypatch):
        """LOG_LEVEL is what agent authors set; letting the pipeline's own threshold
        silently replace it would change behaviour nobody asked to change."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        route_agentex_loggers_to_root()
        assert make_logger("agentex.lib.probe.level").level == logging.DEBUG
