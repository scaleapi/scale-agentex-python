"""Capture client-attested source identity without failing agent builds."""

from __future__ import annotations

import os
import stat
import hashlib
import subprocess
from typing import Optional
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

_GIT_TIMEOUT_S = 5
_HASH_CHUNK_BYTES = 1 << 20


@dataclass(frozen=True)
class BuildProvenance:
    """Source identity for one build; unavailable fields degrade to ``None``."""

    repo: Optional[str] = None
    commit: Optional[str] = None
    ref: Optional[str] = None
    subpath: Optional[str] = None
    working_tree_hash: Optional[str] = None
    dirty: Optional[bool] = None
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    build_timestamp: Optional[str] = None

    def source_fields(self) -> dict[str, object]:
        """The ``source_*`` form fields for the cloud-build upload (None omitted)."""
        fields = {
            "source_repo": self.repo,
            "source_commit": self.commit,
            "source_ref": self.ref,
            "source_subpath": self.subpath,
            "working_tree_hash": self.working_tree_hash,
            "source_dirty": self.dirty,
        }
        return {key: value for key, value in fields.items() if value is not None}

    def build_info(self) -> dict[str, object]:
        """Return provenance using the runtime registration metadata field names."""
        info = {
            "repo": self.repo,
            "commit_hash": self.commit,
            "branch_name": self.ref,
            "subpath": self.subpath,
            "working_tree_hash": self.working_tree_hash,
            "dirty": self.dirty,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "build_timestamp": self.build_timestamp,
        }
        return {key: value for key, value in info.items() if value is not None}


def _git(repo_root: Path, *args: str) -> Optional[str]:
    """Run a git command under ``repo_root``; return stripped stdout or None."""
    try:
        proc = subprocess.run(
            ("git", "-C", str(repo_root), *args),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def normalize_remote(url: Optional[str]) -> Optional[str]:
    """Strip credentials and scheme from a remote, returning ``host/path``."""
    if not url:
        return None
    candidate = url.strip()
    # scp-like syntax: git@host:org/repo(.git) — no scheme, host/path split on ':'
    if "://" not in candidate and ":" in candidate and "/" not in candidate.split(":", 1)[0]:
        candidate = candidate.split("@", 1)[-1].replace(":", "/", 1)
    else:
        if "://" in candidate:
            candidate = candidate.split("://", 1)[1]
        candidate = candidate.split("@", 1)[-1]
    if candidate.endswith(".git"):
        candidate = candidate[: -len(".git")]
    candidate = candidate.strip("/")
    if not candidate:
        return None
    host, slash, path = candidate.partition("/")
    return f"{host.lower()}{slash}{path}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def iter_context_files(root: Path) -> list[Path]:
    """Return files and symlinks under ``root``, sorted by POSIX relative path."""
    return sorted(
        (path for path in root.rglob("*") if path.is_symlink() or path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def working_tree_hash(root: Path) -> str:
    """Hash sorted build inputs, normalized modes, and symlink target strings."""
    lines: list[str] = []
    for path in iter_context_files(root):
        relpath = path.relative_to(root).as_posix()
        if path.is_symlink():
            mode = "120000"
            content_digest = hashlib.sha256(os.readlink(path).encode("utf-8")).hexdigest()
        else:
            executable = bool(path.stat().st_mode & stat.S_IXUSR)
            mode = "100755" if executable else "100644"
            content_digest = _sha256_file(path)
        lines.append(f"{relpath}\x00{mode}\x00{content_digest}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _safe_working_tree_hash(root: Path) -> Optional[str]:
    """Compute the context hash without allowing capture to fail a build."""
    try:
        return working_tree_hash(root)
    except Exception:
        logger.warning("build-provenance: content hash failed; omitting", exc_info=True)
        return None


def capture_build_provenance(
    repo_path: Path, context_root: Path, content_root: Optional[Path] = None
) -> BuildProvenance:
    """Capture git coordinates and the staged build-context hash."""
    timestamp = datetime.now(timezone.utc).isoformat()
    hash_root = content_root if content_root is not None else context_root
    tree_hash = _safe_working_tree_hash(hash_root)

    repo_root = _git(repo_path, "rev-parse", "--show-toplevel")
    if repo_root is None:
        # No git — the content hash is the only identity available.
        logger.info("build-provenance: %s is not a git work tree; content hash only", repo_path)
        return BuildProvenance(working_tree_hash=tree_hash, build_timestamp=timestamp)

    repo_root_path = Path(repo_root)
    commit = _git(repo_root_path, "rev-parse", "HEAD")
    # symbolic-ref fails on a detached HEAD (→ None); fall back to an exact tag.
    ref = _git(repo_root_path, "symbolic-ref", "--short", "HEAD") or _git(
        repo_root_path, "describe", "--tags", "--exact-match"
    )
    remote = normalize_remote(_git(repo_root_path, "remote", "get-url", "origin"))
    author_name = _git(repo_root_path, "log", "-1", "--format=%an")
    author_email = _git(repo_root_path, "log", "-1", "--format=%ae")

    subpath: Optional[str] = None
    try:
        relative = context_root.resolve().relative_to(repo_root_path.resolve()).as_posix()
        subpath = relative if relative != "." else None
    except ValueError:
        subpath = None

    # `git status --porcelain` is empty (→ _git returns None) for a clean tree.
    dirty = _git(repo_root_path, "status", "--porcelain") is not None

    return BuildProvenance(
        repo=remote,
        commit=commit,
        ref=ref,
        subpath=subpath,
        working_tree_hash=tree_hash,
        dirty=dirty,
        author_name=author_name,
        author_email=author_email,
        build_timestamp=timestamp,
    )
