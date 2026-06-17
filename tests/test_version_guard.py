"""Unit tests for the runtime backend version guard (agentex.lib.core.compat.version_guard)."""

from __future__ import annotations

import asyncio

import pytest

from agentex.lib.core.compat import version_guard as vg


def _run(coro):
    return asyncio.run(coro)


def test_parse_versions():
    assert vg._parse("0.2.1") == (0, 2, 1)
    assert vg._parse("v1.4.0") == (1, 4, 0)
    assert vg._parse("0.2.1-rc.1+build5") == (0, 2, 1)
    assert vg._parse("garbage") is None
    assert vg._parse(None) is None


def test_compatible_backend_passes(monkeypatch):
    async def fake(url, **kw):
        return "0.2.0"

    monkeypatch.setattr(vg, "fetch_backend_version", fake)
    # backend (0.2.0) >= min (0.1.0) → no raise
    _run(vg.assert_backend_compatible("http://backend", min_version="0.1.0"))


def test_incompatible_backend_raises(monkeypatch):
    async def fake(url, **kw):
        return "0.0.9"

    monkeypatch.setattr(vg, "fetch_backend_version", fake)
    with pytest.raises(vg.IncompatibleBackendError) as exc:
        _run(vg.assert_backend_compatible("http://backend", min_version="0.1.0", sdk_version="0.13.0"))
    msg = str(exc.value)
    assert "0.13.0" in msg and "0.1.0" in msg and "0.0.9" in msg  # actionable message


def test_skip_env_bypasses(monkeypatch):
    async def fake(url, **kw):
        raise AssertionError("must not fetch when skip env is set")

    monkeypatch.setattr(vg, "fetch_backend_version", fake)
    monkeypatch.setenv(vg.SKIP_ENV, "1")
    # even an impossible min must not raise when explicitly skipped
    _run(vg.assert_backend_compatible("http://backend", min_version="9.9.9"))


def test_unknown_backend_version_does_not_crash(monkeypatch):
    async def fake(url, **kw):
        return None  # unreachable / no version → unknown

    monkeypatch.setattr(vg, "fetch_backend_version", fake)
    # unknown version warns but must not raise (transient/contract-less server)
    _run(vg.assert_backend_compatible("http://backend", min_version="9.9.9"))


def test_no_base_url_is_noop():
    _run(vg.assert_backend_compatible(None))
    _run(vg.assert_backend_compatible(""))
