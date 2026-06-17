"""Unit tests for the runtime backend version guard (agentex.lib.core.compat.version_guard)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from agentex.lib.core.compat import version_guard as vg


def _run(coro):
    return asyncio.run(coro)


def _patch_transport(monkeypatch, handler):
    """Make version_guard's httpx.AsyncClient route through an in-memory MockTransport,
    so fetch_backend_version runs for real (request build, status check, JSON parse)
    without touching the network. `handler(request) -> httpx.Response` (or raises)."""

    real_client = httpx.AsyncClient  # capture before patching to avoid recursing into the factory

    def factory(**kwargs):
        kwargs.pop("transport", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(vg.httpx, "AsyncClient", factory)


def test_parse_versions():
    assert vg._parse("0.2.1") == (0, 2, 1, None)
    assert vg._parse("v1.4.0") == (1, 4, 0, None)
    assert vg._parse("0.2.1-rc.1+build5") == (0, 2, 1, "rc.1")  # build metadata ignored
    assert vg._parse("0.1.0+build5") == (0, 1, 0, None)  # build metadata only, still stable
    assert vg._parse("garbage") is None
    assert vg._parse(None) is None


def test_parse_rejects_malformed_tails():
    # Anchored regex: a junk tail after the triplet must NOT silently parse as stable 0.1.0;
    # it has to fall through to None (→ unknown / unparseable path), not satisfy the floor.
    for bad in ("0.1.0rc1", "0.1.0foo", "0.1.0.1", "0.1.0-", "1.2", "0.1.0-rc 1"):
        assert vg._parse(bad) is None, bad


def test_parse_anchored_both_ends():
    # Leading anchor (^): anything before the triplet (other than whitespace / a `v`) is rejected.
    for bad in ("foo0.1.0", ">=0.1.0", "x0.1.0", "=0.1.0", "0 0.1.0"):
        assert vg._parse(bad) is None, bad
    # Trailing anchor ($): anything after the version (other than whitespace) is rejected.
    for bad in ("0.1.0 extra", "0.1.0;", "0.1.0/", "0.1.0+", "0.1.0 0.1.0"):
        assert vg._parse(bad) is None, bad
    # What the anchors DO permit: surrounding whitespace and an optional leading `v`.
    assert vg._parse(" 0.1.0 ") == (0, 1, 0, None)
    assert vg._parse("\tv1.2.3\n") == (1, 2, 3, None)
    assert vg._parse(" 0.2.0-rc.1 ") == (0, 2, 0, "rc.1")


def test_prerelease_precedence():
    k = lambda v: vg._precedence_key(vg._parse(v))  # noqa: E731
    assert k("0.1.0-rc.1") < k("0.1.0")       # prerelease precedes its stable release (SemVer §11)
    assert k("0.1.0-rc.1") < k("0.1.0-rc.2")  # numeric prerelease identifiers compare numerically
    assert k("0.1.0-alpha") < k("0.1.0-rc")   # numeric/alpha ordering by identifier
    assert k("0.1.0") < k("0.1.1-rc.1")       # patch bump outranks prior stable
    assert k("0.2.0-rc.1") > k("0.1.0")       # prerelease of a higher version still clears the floor


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


def test_prerelease_backend_below_stable_floor_raises(monkeypatch):
    async def fake(url, **kw):
        return "0.1.0-rc.1"  # release candidate: precedes the stable 0.1.0 contract

    monkeypatch.setattr(vg, "fetch_backend_version", fake)
    with pytest.raises(vg.IncompatibleBackendError):
        _run(vg.assert_backend_compatible("http://backend", min_version="0.1.0", sdk_version="0.13.0"))


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


def test_truthy(monkeypatch):
    for val in ("1", "true", "True", "YES", "on"):
        monkeypatch.setenv("X_GUARD_FLAG", val)
        assert vg._truthy("X_GUARD_FLAG")
    for val in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("X_GUARD_FLAG", val)
        assert not vg._truthy("X_GUARD_FLAG")
    monkeypatch.delenv("X_GUARD_FLAG", raising=False)
    assert not vg._truthy("X_GUARD_FLAG")  # unset → falsy


# --- fetch_backend_version: exercised for real through MockTransport (not mocked out) ---


def test_fetch_success_and_url_construction(monkeypatch):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["method"] = request.method
        return httpx.Response(200, json={"openapi": "3.1.0", "info": {"version": "0.2.0"}})

    _patch_transport(monkeypatch, handler)
    assert _run(vg.fetch_backend_version("http://backend/")) == "0.2.0"
    assert seen["url"] == "http://backend/openapi.json"  # trailing slash trimmed, path appended
    assert seen["method"] == "GET"


def test_fetch_missing_version_field(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"info": {}}))
    assert _run(vg.fetch_backend_version("http://backend")) is None


def test_fetch_missing_info_object(monkeypatch):
    # `info` absent entirely, and `info: null` — both must coalesce to None, not crash.
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={}))
    assert _run(vg.fetch_backend_version("http://backend")) is None
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"info": None}))
    assert _run(vg.fetch_backend_version("http://backend")) is None


def test_fetch_http_error_status(monkeypatch):
    # raise_for_status() → caught → None (e.g. server has no /openapi.json)
    _patch_transport(monkeypatch, lambda r: httpx.Response(404, text="not found"))
    assert _run(vg.fetch_backend_version("http://backend")) is None
    _patch_transport(monkeypatch, lambda r: httpx.Response(503, text="unavailable"))
    assert _run(vg.fetch_backend_version("http://backend")) is None


def test_fetch_non_json_body(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, text="<html>nope</html>"))
    assert _run(vg.fetch_backend_version("http://backend")) is None


def test_fetch_connection_error(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    _patch_transport(monkeypatch, handler)
    assert _run(vg.fetch_backend_version("http://backend")) is None


# --- assert_backend_compatible end-to-end: real fetch through MockTransport, not mocked out ---


def test_assert_end_to_end_old_backend_raises(monkeypatch):
    monkeypatch.delenv(vg.SKIP_ENV, raising=False)
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"info": {"version": "0.0.9"}}))
    with pytest.raises(vg.IncompatibleBackendError):
        _run(vg.assert_backend_compatible("http://backend", min_version="0.1.0", sdk_version="0.13.0"))


def test_assert_end_to_end_new_backend_passes(monkeypatch):
    monkeypatch.delenv(vg.SKIP_ENV, raising=False)
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"info": {"version": "0.2.0"}}))
    _run(vg.assert_backend_compatible("http://backend", min_version="0.1.0"))


def test_assert_end_to_end_unreachable_backend_does_not_raise(monkeypatch):
    # real fetch returns None on connection failure → guard proceeds (no crash on transient blip)
    monkeypatch.delenv(vg.SKIP_ENV, raising=False)

    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    _patch_transport(monkeypatch, handler)
    _run(vg.assert_backend_compatible("http://backend", min_version="9.9.9"))
