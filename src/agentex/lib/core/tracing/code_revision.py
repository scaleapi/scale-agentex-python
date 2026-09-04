"""Opt-in stamping of the agent's source commit onto its spans.

Nothing is stamped until the agent calls :func:`enable`, mirroring the
``lineage`` registry next door: a process-wide switch the agent sets once at
import, rather than automatic behaviour every agent inherits. When enabled the
resolved commit lands in span data under ``__commit_sha__`` and is searchable in
the SGP Traces UI as ``__commit_sha__:<sha>``.

This is deliberately separate from ``__agent_version__``, which is automatic and
carries the deployed image tag verbatim ("image tag or git sha"). That tag is a
real commit on some build paths but an ``<image-name>-<sha>`` composite (AWS
ECR), ``latest``, or a hand-passed tag on others -- so a field named for a commit
must not simply mirror it. Values that are not git object names are refused, and
a field named ``__commit_sha__`` therefore only ever holds one.
"""

from __future__ import annotations

import os
import re

from agentex.lib.utils.logging import make_logger

__all__ = ("COMMIT_SHA_KEY", "enable", "disable", "is_enabled", "commit_sha", "is_git_object_name")

logger = make_logger(__name__)

COMMIT_SHA_KEY = "__commit_sha__"

# A git object name: 40 hex for SHA-1, 64 for SHA-256, or an abbreviation down to
# git's own 7-character minimum.
_GIT_SHA_RE = re.compile(r"[0-9a-fA-F]{7,64}")


def is_git_object_name(value: str) -> bool:
    """Whether ``value`` is a full or abbreviated git SHA-1/SHA-256 object name."""
    return _GIT_SHA_RE.fullmatch(value.strip()) is not None


_COMMIT_SHA_ENV = "AGENT_COMMIT_SHA"
# Fallback only: automatic, and only usable when it happens to be SHA-shaped.
_AGENT_VERSION_ENV = "AGENT_VERSION"

# Resolved once at enable() rather than per span: the value is fixed for the
# life of the process, and resolving eagerly means a bad value is reported at
# startup instead of silently producing unstamped spans.
_commit_sha: str | None = None


def enable(commit_sha: str | None = None) -> None:
    """Opt this process in to stamping ``__commit_sha__`` onto every span.

    Value precedence: the explicit ``commit_sha`` argument, else
    ``AGENT_COMMIT_SHA``, else ``AGENT_VERSION`` when the deployment happened to
    set it to a bare commit SHA. A value that is not a git object name is
    refused with a warning and leaves stamping off -- better an absent field
    than one named for a commit that holds an image tag.
    """
    global _commit_sha

    for value, source in (
        (commit_sha, "the commit_sha argument"),
        (os.environ.get(_COMMIT_SHA_ENV), _COMMIT_SHA_ENV),
        (os.environ.get(_AGENT_VERSION_ENV), _AGENT_VERSION_ENV),
    ):
        candidate = (value or "").strip()
        if not candidate:
            continue
        if _GIT_SHA_RE.fullmatch(candidate):
            _commit_sha = candidate
            logger.info("code revision stamping enabled from %s", source)
            return
        # An explicit argument or AGENT_COMMIT_SHA is a direct statement of
        # intent, so a bad value there is worth surfacing. AGENT_VERSION is only
        # a fallback and is expected to be a non-SHA tag much of the time, so
        # falling through it quietly is correct, not a silent failure.
        if source != _AGENT_VERSION_ENV:
            logger.warning(
                "%s=%r is not a git commit SHA; __commit_sha__ will not be stamped.",
                source,
                candidate,
            )
            _commit_sha = None
            return

    _commit_sha = None
    logger.warning(
        "code revision stamping was enabled but no commit SHA was found "
        "(checked the commit_sha argument, %s, and %s); __commit_sha__ will not "
        "be stamped. Set %s in the agent's environment -- e.g. bake it at build "
        "time with a Dockerfile ARG/ENV.",
        _COMMIT_SHA_ENV,
        _AGENT_VERSION_ENV,
        _COMMIT_SHA_ENV,
    )


def disable() -> None:
    """Turn stamping back off (also used for test isolation)."""
    global _commit_sha
    _commit_sha = None


def is_enabled() -> bool:
    """Whether a commit SHA resolved and will be stamped."""
    return _commit_sha is not None


def commit_sha() -> str | None:
    """The resolved commit SHA, or ``None`` when stamping is not enabled."""
    return _commit_sha
