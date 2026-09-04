"""Tests for the agentex-client compatibility guard (0.13.0 split regression)."""

from __future__ import annotations

import pytest

import agentex.lib._version_guard as guard


def test_passes_when_surface_present() -> None:
    guard.verify_client_compatibility()  # full client surface installed


def test_newer_client_not_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    # Version is not a gate: a newer client (additive) with the full surface passes.
    monkeypatch.setattr(guard, "version", lambda pkg: "0.14.0" if pkg == "agentex-client" else "0.13.0")
    guard.verify_client_compatibility()


def test_raises_when_client_surface_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    import agentex.types

    # A partial install missing a needed symbol fails with an actionable error.
    monkeypatch.delattr(agentex.types, "Event", raising=False)
    with pytest.raises(ImportError, match="could not import the agentex-client REST surface"):
        guard.verify_client_compatibility()
