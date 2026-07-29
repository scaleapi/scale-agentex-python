from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agentex.lib.utils.build_provenance import (
    normalize_remote,
    working_tree_hash,
    iter_context_files,
    capture_build_provenance,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(("git", "-C", str(repo), *args), check=True, capture_output=True, text=True)


def _init_repo(path: Path, *, remote: str | None = "git@github.com:scaleapi/demo.git") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "dev@scale.com")
    _git(path, "config", "user.name", "Dev")
    _git(path, "config", "commit.gpgsign", "false")
    if remote:
        _git(path, "remote", "add", "origin", remote)
    return path


def _commit_all(path: Path, message: str = "init") -> None:
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", message)
    _git(path, "branch", "-M", "main")


def _write(root: Path, rel: str, content: str = "x") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


# --- normalize_remote ---------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("git@github.com:scaleapi/Repo.git", "github.com/scaleapi/Repo"),
        ("https://github.com/scaleapi/Repo.git", "github.com/scaleapi/Repo"),
        ("https://x-token:secret@GitHub.com/scaleapi/Repo", "github.com/scaleapi/Repo"),
        ("ssh://git@gitlab.com/group/sub/proj.git", "gitlab.com/group/sub/proj"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_remote(raw: str | None, expected: str | None) -> None:
    assert normalize_remote(raw) == expected


# --- working_tree_hash --------------------------------------------------------


def test_hash_is_order_independent(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    for rel in ("z.txt", "a/b.txt", "m.txt"):
        _write(first, rel, rel)
    # Same content, different creation order.
    for rel in ("m.txt", "z.txt", "a/b.txt"):
        _write(second, rel, rel)
    assert working_tree_hash(first) == working_tree_hash(second)


def test_hash_changes_on_one_byte(tmp_path: Path) -> None:
    root = tmp_path / "ctx"
    _write(root, "f.txt", "hello")
    before = working_tree_hash(root)
    _write(root, "f.txt", "hellp")
    assert working_tree_hash(root) != before


def test_hash_changes_when_file_added(tmp_path: Path) -> None:
    root = tmp_path / "ctx"
    _write(root, "f.txt", "hello")
    before = working_tree_hash(root)
    _write(root, "g.txt", "new")
    assert working_tree_hash(root) != before


def test_hash_changes_on_executable_bit(tmp_path: Path) -> None:
    root = tmp_path / "ctx"
    script = root / "run.sh"
    _write(root, "run.sh", "#!/bin/sh\n")
    before = working_tree_hash(root)
    script.chmod(0o755)
    assert working_tree_hash(root) != before


def test_symlink_hashes_target_not_resolved_content(tmp_path: Path) -> None:
    root = tmp_path / "ctx"
    root.mkdir()
    # Dangling symlinks: distinct hashes prove the target string is hashed, not
    # resolved content (resolving would raise).
    (root / "link").symlink_to("points/to/a")
    hash_a = working_tree_hash(root)
    (root / "link").unlink()
    (root / "link").symlink_to("points/to/b")
    assert working_tree_hash(root) != hash_a


def test_iter_context_files_skips_directories(tmp_path: Path) -> None:
    root = tmp_path / "ctx"
    _write(root, "pkg/mod.py", "x")
    _write(root, "top.txt", "y")
    rels = [path.relative_to(root).as_posix() for path in iter_context_files(root)]
    assert rels == ["pkg/mod.py", "top.txt"]


# --- capture_build_provenance -------------------------------------------------


def test_capture_clean_tree(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _write(repo, "main.py", "print(1)")
    _commit_all(repo)

    prov = capture_build_provenance(repo, repo)

    assert prov.repo == "github.com/scaleapi/demo"
    assert prov.ref == "main"
    assert prov.commit is not None and len(prov.commit) == 40
    assert prov.working_tree_hash is not None  # always computed
    assert prov.dirty is False
    assert prov.subpath is None
    assert prov.author_email == "dev@scale.com"


def test_capture_untracked_file_changes_hash(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _write(repo, "main.py", "print(1)")
    _commit_all(repo)
    _write(repo, "scratch.py", "debug = True")  # untracked

    prov = capture_build_provenance(repo, repo)

    # The stale-code guard: an untracked file is part of the build context, so it
    # must move the hash (a `git diff` of tracked files alone would miss it).
    assert prov.dirty is True
    assert prov.working_tree_hash == working_tree_hash(repo)
    assert working_tree_hash(repo) != _hash_without(repo, "scratch.py")


def _hash_without(repo: Path, rel: str) -> str:
    removed = repo / rel
    saved = removed.read_text()
    removed.unlink()
    try:
        return working_tree_hash(repo)
    finally:
        removed.write_text(saved)


def test_capture_detached_head_has_no_ref(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _write(repo, "main.py", "print(1)")
    _commit_all(repo)
    _write(repo, "main.py", "print(2)")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "second")
    first = subprocess.run(
        ("git", "-C", str(repo), "rev-list", "--max-parents=0", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _git(repo, "checkout", "-q", first)

    prov = capture_build_provenance(repo, repo)

    assert prov.commit == first
    assert prov.ref is None


def test_capture_detached_on_tag_uses_tag(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _write(repo, "main.py", "print(1)")
    _commit_all(repo)
    _git(repo, "tag", "v1.2.3")
    _git(repo, "checkout", "-q", "v1.2.3")

    assert capture_build_provenance(repo, repo).ref == "v1.2.3"


def test_capture_no_remote(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo", remote=None)
    _write(repo, "main.py", "print(1)")
    _commit_all(repo)

    prov = capture_build_provenance(repo, repo)

    assert prov.repo is None
    assert prov.commit is not None
    assert prov.working_tree_hash is not None  # always computed


def test_capture_non_git_dir(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    _write(plain, "main.py", "print(1)")

    prov = capture_build_provenance(plain, plain)

    assert prov.repo is None
    assert prov.commit is None
    assert prov.ref is None
    # No commit → the content hash is the identity; dirtiness is undefined (no VCS).
    assert prov.working_tree_hash == working_tree_hash(plain)
    assert prov.dirty is None
    assert prov.build_timestamp is not None


def test_capture_never_raises_when_hash_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import agentex.lib.utils.build_provenance as bp

    plain = tmp_path / "plain"  # non-git → would hash, which we force to fail
    _write(plain, "main.py", "print(1)")

    def _boom(_root: Path) -> str:
        raise OSError("permission denied")

    monkeypatch.setattr(bp, "working_tree_hash", _boom)

    prov = bp.capture_build_provenance(plain, plain)  # must not raise

    assert prov.working_tree_hash is None


def test_capture_monorepo_subpath(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _write(repo, "agents/foo/main.py", "print(1)")
    _commit_all(repo)

    prov = capture_build_provenance(repo, repo / "agents" / "foo")

    assert prov.subpath == "agents/foo"


def test_capture_monorepo_ignores_changes_outside_context(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _write(repo, "agents/foo/main.py", "print(1)")
    _write(repo, "agents/bar/main.py", "print(2)")
    _commit_all(repo)
    _write(repo, "agents/bar/scratch.py", "debug = True")

    prov = capture_build_provenance(repo, repo / "agents" / "foo")

    assert prov.dirty is False
