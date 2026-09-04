"""Fail fast with a clear error on an incomplete agentex-client install instead
of a cryptic `cannot import name ... from agentex.types`."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def _installed(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "unknown"


def verify_client_compatibility() -> None:
    # Canary on the client REST surface, not the version: newer clients are fine
    # (additive); we only fail if a symbol/resource the ADK needs is absent.
    try:
        from agentex.types import Event as _Event  # noqa: F401
        from agentex.resources import states as _states  # noqa: F401
    except (ImportError, AttributeError) as exc:
        raise ImportError(
            f"agentex-sdk could not import the agentex-client REST surface it "
            f"depends on (agentex-sdk={_installed('agentex-sdk')}, "
            f"agentex-client={_installed('agentex-client')}). Reinstall both at a "
            f"compatible version, e.g. `pip install --force-reinstall agentex-sdk`."
        ) from exc
