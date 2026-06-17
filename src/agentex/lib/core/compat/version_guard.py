"""Runtime SDK ↔ backend contract-version guard.

Complements the *build-time* cross-version compatibility tests (``tests/compat``):

- **Build-time** (CI): is this *client* compatible with the window of supported server
  contracts (``min-supported``..``current``)?
- **Runtime** (this module): is the *server* the SDK is pointed at within that window?

It runs once at ACP/worker startup, reads the backend's contract version (the version
the server already reports via ``/openapi.json`` ``info.version``), and **fails fast with
an actionable error** if the backend is older than this SDK supports — instead of the
mismatch surfacing later as opaque 500s / missing-field errors deep in a request.

``MIN_BACKEND_CONTRACT`` is the same source of truth as the ``min-supported`` server
contract in ``tests/compat/server_specs/manifest.json``: the oldest agentex backend this
SDK version supports. Bump both together when a breaking change raises the floor.
"""

from __future__ import annotations

import os
import re

import httpx

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

# Oldest agentex backend contract this SDK is compatible with.
# Keep in sync with the `min-supported` spec in tests/compat (#407); the version axis
# itself comes from scale-agentex release tags (#321). Bump on a breaking SDK change.
MIN_BACKEND_CONTRACT = "0.1.0"

SKIP_ENV = "AGENTEX_SKIP_VERSION_CHECK"

_VERSION_RE = re.compile(r"^\s*v?(\d+)\.(\d+)\.(\d+)")


class IncompatibleBackendError(RuntimeError):
    """Raised when the agentex backend is older than this SDK's minimum supported contract."""


def _parse(version: str | None) -> tuple[int, int, int] | None:
    m = _VERSION_RE.match(version or "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


async def fetch_backend_version(base_url: str, *, timeout: float = 5.0) -> str | None:
    """Return the backend's reported contract version (``/openapi.json`` ``info.version``), or None."""
    url = base_url.rstrip("/") + "/openapi.json"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return (resp.json().get("info") or {}).get("version")
    except Exception as exc:  # noqa: BLE001 - any failure → unknown, handled by caller
        logger.warning("backend version guard: could not fetch %s (%s)", url, exc)
        return None


async def assert_backend_compatible(
    base_url: str | None,
    *,
    min_version: str = MIN_BACKEND_CONTRACT,
    sdk_version: str | None = None,
) -> None:
    """Fail fast at startup if the backend is older than ``min_version``.

    No-op (warns, does not raise) when:
      - ``AGENTEX_SKIP_VERSION_CHECK`` is set (explicit bypass),
      - ``base_url`` is unset,
      - the backend version can't be determined (unreachable / unparseable) — a transient
        blip or a contract-less server shouldn't crash startup.

    Raises ``IncompatibleBackendError`` only when the backend version is *known* and older
    than ``min_version``.
    """
    if _truthy(SKIP_ENV):
        logger.warning("%s set — skipping backend version guard", SKIP_ENV)
        return
    if not base_url:
        return

    if sdk_version is None:
        from agentex._version import __version__ as sdk_version  # local import to avoid cycles

    backend_version = await fetch_backend_version(base_url)
    if backend_version is None:
        logger.warning(
            "backend version guard: could not determine backend version at %s; proceeding "
            "(set %s=1 to silence).",
            base_url,
            SKIP_ENV,
        )
        return

    backend, minimum = _parse(backend_version), _parse(min_version)
    if backend is None or minimum is None:
        logger.warning(
            "backend version guard: unparseable version(s) backend=%r min=%r; proceeding.",
            backend_version,
            min_version,
        )
        return

    if backend < minimum:
        raise IncompatibleBackendError(
            f"agentex-sdk {sdk_version} requires agentex backend >= {min_version}, "
            f"but {base_url} reports {backend_version}. "
            f"Upgrade the backend, or pin agentex-sdk to a version compatible with backend "
            f"{backend_version}. (Set {SKIP_ENV}=1 to bypass at your own risk.)"
        )

    logger.info(
        "backend version guard OK: sdk=%s backend=%s (min=%s)",
        sdk_version,
        backend_version,
        min_version,
    )
