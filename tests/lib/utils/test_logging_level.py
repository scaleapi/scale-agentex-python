"""Tests for log level resolution in agentex.lib.utils.logging.

The level used to be pinned to INFO with no override, so a debug() call could
never be emitted on any configuration. That is not just a missing feature: it
made diagnostics that were already written into the SDK unreachable.
"""

from __future__ import annotations

import logging

import pytest

from agentex.lib.utils.logging import (
    DEFAULT_LOG_LEVEL,
    make_logger,
    resolve_log_level,
)


def test_defaults_to_info_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    assert resolve_log_level() == DEFAULT_LOG_LEVEL == logging.INFO


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("DEBUG", logging.DEBUG),
        ("debug", logging.DEBUG),
        ("  WaRnInG  ", logging.WARNING),
        ("ERROR", logging.ERROR),
        ("CRITICAL", logging.CRITICAL),
    ],
)
def test_reads_level_from_env(
    monkeypatch: pytest.MonkeyPatch, configured: str, expected: int
) -> None:
    monkeypatch.setenv("LOG_LEVEL", configured)

    assert resolve_log_level() == expected


@pytest.mark.parametrize("configured", ["", "   ", "VERBOSE", "10x", "TRUE"])
def test_falls_back_to_info_on_an_unusable_value(
    monkeypatch: pytest.MonkeyPatch, configured: str
) -> None:
    """A typo must not silently disable logging.

    logging.getLevelName returns the string "Level FOO" for anything it does not
    recognise, which would otherwise be handed straight to setLevel.
    """
    monkeypatch.setenv("LOG_LEVEL", configured)

    assert resolve_log_level() == logging.INFO


def test_make_logger_applies_the_configured_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """The regression that mattered: a debug() call must be able to emit."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    logger = make_logger("agentex.tests.level_from_env")

    assert logger.level == logging.DEBUG
    assert logger.isEnabledFor(logging.DEBUG)
