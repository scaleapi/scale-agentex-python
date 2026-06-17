"""Runtime check that warns when the agentex server's contract version is older
than this SDK supports — the runtime complement to the build-time compat suite."""

from __future__ import annotations

import os

import httpx

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

# Header the agentex server sets to advertise its release/contract version.
SERVER_VERSION_HEADER = "x-agentex-version"

# Oldest server contract this SDK supports. Keep in sync with the compat suite's
# `min-supported` (tests/compat/server_specs/manifest.json); advance it whenever
# the SDK drops support for an older server contract.
MIN_SUPPORTED_SERVER_VERSION = "0.1.0"

_STRICT_ENV = "AGENTEX_STRICT_SERVER_VERSION"

_warned = False  # warn once per process — the header rides every response


def _parse(version: str) -> tuple[int, int, int] | None:
    parts = version.strip().lstrip("v").split(".")[:3]
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def check_server_version(server_version: str | None) -> None:
    """Warn once (or raise under AGENTEX_STRICT_SERVER_VERSION) if the server is
    older than MIN_SUPPORTED_SERVER_VERSION. No-op when the header is absent or
    unparseable — servers predating the header can't be identified."""
    global _warned
    if _warned or not server_version:
        return
    server, floor = _parse(server_version), _parse(MIN_SUPPORTED_SERVER_VERSION)
    if server is None or floor is None or server >= floor:
        return
    _warned = True
    msg = (
        f"agentex server version {server_version} is older than the minimum this SDK "
        f"supports ({MIN_SUPPORTED_SERVER_VERSION}); requests may fail or silently "
        f"lose data. Upgrade the server or pin an older agentex-sdk."
    )
    if os.environ.get(_STRICT_ENV):
        raise RuntimeError(msg)
    logger.warning(msg)


def install_on(http_client: httpx.AsyncClient) -> None:
    """Attach a response hook that checks the server version header on each call."""

    async def _hook(response: httpx.Response) -> None:
        check_server_version(response.headers.get(SERVER_VERSION_HEADER))

    http_client.event_hooks.setdefault("response", []).append(_hook)
